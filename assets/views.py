from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.decorators import admin_or_technician_required, admin_required

from .forms import AssetAssignmentForm, AssetFilterForm, AssetForm, LocationForm, MaintenanceRecordForm
from .models import (
    Asset,
    AssetAssignment,
    AssetCategory,
    AssetDepreciation,
    AssetType,
    Location,
    MaintenanceRecord,
)


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


# Begin asset_list view
@login_required
def asset_list(request):
    assets = Asset.objects.select_related(
        "category",
        "asset_type",
        "department",
        "purchase",
        "depreciation",
    )
    filter_form = AssetFilterForm(request.GET or None)

    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        if search:
            assets = assets.filter(
                Q(asset_tag__icontains=search)
                | Q(name__icontains=search)
                | Q(serial_number__icontains=search)
            )

        category = filter_form.cleaned_data.get("category")
        if category:
            assets = assets.filter(category=category)

        asset_type = filter_form.cleaned_data.get("asset_type")
        if asset_type:
            assets = assets.filter(asset_type=asset_type)

        department = filter_form.cleaned_data.get("department")
        if department:
            assets = assets.filter(department=department)

        status = filter_form.cleaned_data.get("status")
        if status:
            assets = assets.filter(status=status)

        is_active = filter_form.cleaned_data.get("is_active")
        if is_active == "true":
            assets = assets.filter(is_active=True)
        elif is_active == "false":
            assets = assets.filter(is_active=False)

    paginator = Paginator(assets.order_by("asset_tag"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "filter_form": filter_form,
        "filter_querystring": request.GET.copy(),
        "stats": {
            "total": Asset.objects.count(),
            "available": Asset.objects.filter(status=Asset.STATUS_AVAILABLE).count(),
            "assigned": Asset.objects.filter(status=Asset.STATUS_ASSIGNED).count(),
            "maintenance": Asset.objects.filter(status=Asset.STATUS_MAINTENANCE).count(),
        },
    }

    context["filter_querystring"].pop("page", None)

    if _is_htmx(request):
        return render(request, "assets/partials/asset_list_content.html", context)

    return render(request, "assets/asset_list.html", context)
# End asset_list view


# Begin asset_detail view
@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(
        Asset.objects.select_related("category", "asset_type", "department", "purchase", "depreciation"),
        pk=pk,
    )
    try:
        depreciation = asset.depreciation
    except AssetDepreciation.DoesNotExist:
        depreciation = None
    context = {
        "asset": asset,
        "depreciation": depreciation,
        "current_assignment": asset.current_assignment,
        "current_location": asset.current_location,
        "location_history": asset.location_history.select_related("location", "moved_by")[:10],
        "assignments": asset.assignments.select_related("issued_by")[:10],
        "maintenance_records": asset.maintenance_records.all()[:10],
        "installed_software": asset.installed_software.select_related("software", "installed_by")[:10],
        "attribute_values": asset.attribute_values.select_related("attribute")[:10],
        "activity_logs": asset.activity_logs.select_related("performed_by")[:10],
    }
    return render(request, "assets/asset_detail.html", context)
# End asset_detail view


# Begin asset_create view
@login_required
@admin_or_technician_required
def asset_create(request):
    if request.method == "POST":
        form = AssetForm(request.POST, user=request.user)
        if form.is_valid():
            asset = form.save()
            messages.success(request, f"Asset {asset.asset_tag} created successfully.")
            return redirect("assets:asset_detail", pk=asset.pk)
    else:
        form = AssetForm(user=request.user)

    return render(
        request,
        "assets/asset_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Asset",
        },
    )
# End asset_create view


# Begin asset_type_field view
@login_required
@admin_or_technician_required
def asset_type_field(request):
    category_id = request.GET.get("category")
    selected_asset_type_id = request.GET.get("asset_type")
    asset_types = AssetType.objects.none()

    if category_id:
        asset_types = AssetType.objects.filter(category_id=category_id).order_by("name")

    return render(
        request,
        "assets/partials/asset_type_field.html",
        {
            "asset_types": asset_types,
            "selected_asset_type_id": str(selected_asset_type_id or ""),
        },
    )
# End asset_type_field view


# Begin asset_update view
@login_required
@admin_or_technician_required
def asset_update(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        form = AssetForm(request.POST, instance=asset, user=request.user)
        if form.is_valid():
            asset = form.save()
            messages.success(request, f"Asset {asset.asset_tag} updated successfully.")
            return redirect("assets:asset_detail", pk=asset.pk)
    else:
        form = AssetForm(instance=asset, user=request.user)

    return render(
        request,
        "assets/asset_form.html",
        {
            "form": form,
            "asset": asset,
            "action": "Update",
            "page_title": f"Update {asset.asset_tag}",
        },
    )
# End asset_update view


# Begin asset_delete view
@login_required
@admin_or_technician_required
@require_http_methods(["GET", "POST"])
def asset_delete(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        asset_tag = asset.asset_tag
        asset.delete()
        messages.success(request, f"Asset {asset_tag} deleted successfully.")
        return redirect("assets:asset_list")

    return render(request, "assets/asset_confirm_delete.html", {"asset": asset})
# End asset_delete view


# Begin asset_qr_code view
@login_required
def asset_qr_code(request, pk):
    import qrcode

    asset = get_object_or_404(Asset, pk=pk)
    location = asset.current_location or "Unknown location"
    qr_data = f"ICT-ASSET:{asset.asset_tag}|{asset.name}|{location}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="{asset.asset_tag}_qr.png"'
    return response
# End asset_qr_code view


# Begin category_list view
@login_required
def category_list(request):
    categories = AssetCategory.objects.ordered_choices().annotate(
        asset_count=Count("assets"),
        type_count=Count("types"),
    )
    return render(request, "assets/category_list.html", {"categories": categories})
# End category_list view


# Begin location_list view
@login_required
@admin_required
def location_list(request):
    locations = Location.objects.annotate(asset_count=Count("asset_history__asset", distinct=True))
    search = request.GET.get("search", "").strip()

    if search:
        locations = locations.filter(
            Q(name__icontains=search)
            | Q(building__icontains=search)
            | Q(room__icontains=search)
            | Q(description__icontains=search)
        )

    paginator = Paginator(locations.order_by("name", "building", "room"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "search": search,
        "filter_querystring": filter_querystring,
        "stats": {
            "total": Location.objects.count(),
            "assigned": Location.objects.filter(asset_history__isnull=False).distinct().count(),
            "unused": Location.objects.filter(asset_history__isnull=True).count(),
        },
    }
    return render(request, "assets/location_list.html", context)


# End location_list view


# Begin location_detail view
@login_required
@admin_required
def location_detail(request, pk):
    location = get_object_or_404(
        Location.objects.annotate(asset_count=Count("asset_history__asset", distinct=True)),
        pk=pk,
    )
    history = location.asset_history.select_related("asset", "moved_by").order_by("-moved_at")[:15]
    return render(
        request,
        "assets/location_detail.html",
        {
            "location": location,
            "history": history,
        },
    )


# End location_detail view


# Begin location_create view
@login_required
@admin_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            messages.success(request, f"Location {location} created successfully.")
            return redirect("assets:location_detail", pk=location.pk)
    else:
        form = LocationForm()

    return render(
        request,
        "assets/location_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Location",
        },
    )


# End location_create view


# Begin location_update view
@login_required
@admin_required
def location_update(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if request.method == "POST":
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            location = form.save()
            messages.success(request, f"Location {location} updated successfully.")
            return redirect("assets:location_detail", pk=location.pk)
    else:
        form = LocationForm(instance=location)

    return render(
        request,
        "assets/location_form.html",
        {
            "form": form,
            "location": location,
            "action": "Update",
            "page_title": f"Update {location}",
        },
    )


# End location_update view


# Begin location_delete view
@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def location_delete(request, pk):
    location = get_object_or_404(
        Location.objects.annotate(asset_count=Count("asset_history__asset", distinct=True)),
        pk=pk,
    )

    if request.method == "POST":
        location_name = str(location)
        try:
            location.delete()
        except ProtectedError:
            messages.error(
                request,
                "This location cannot be deleted because it is referenced in asset location history.",
            )
            return redirect("assets:location_detail", pk=location.pk)
        messages.success(request, f"Location {location_name} deleted successfully.")
        return redirect("assets:location_list")

    return render(
        request,
        "assets/location_confirm_delete.html",
        {"location": location},
    )


# End location_delete view


# Begin assignment_list view
@login_required
def assignment_list(request):
    assignments = AssetAssignment.objects.select_related("asset", "issued_by")
    stats_queryset = AssetAssignment.objects.all()
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "").strip()
    asset_id = request.GET.get("asset", "").strip()
    selected_asset = None

    if asset_id:
        selected_asset = Asset.objects.filter(pk=asset_id).first()
        if selected_asset:
            assignments = assignments.filter(asset=selected_asset)
            stats_queryset = stats_queryset.filter(asset=selected_asset)

    if search:
        assignments = assignments.filter(
            Q(asset__asset_tag__icontains=search)
            | Q(asset__name__icontains=search)
            | Q(assignee_identifier__icontains=search)
            | Q(assignee_name__icontains=search)
            | Q(assignee_contact__icontains=search)
            | Q(issued_by__email__icontains=search)
            | Q(issued_by__first_name__icontains=search)
            | Q(issued_by__last_name__icontains=search)
            | Q(purpose__icontains=search)
        )

    if state == "active":
        assignments = assignments.filter(returned_date__isnull=True)
    elif state == "returned":
        assignments = assignments.filter(returned_date__isnull=False)

    paginator = Paginator(assignments.order_by("-assigned_date", "-id"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "search": search,
        "state": state,
        "selected_asset": selected_asset,
        "filter_querystring": filter_querystring,
        "stats": {
            "total": stats_queryset.count(),
            "active": stats_queryset.filter(returned_date__isnull=True).count(),
            "returned": stats_queryset.filter(returned_date__isnull=False).count(),
        },
    }
    return render(request, "assets/assignment_list.html", context)
# End assignment_list view


# Begin assignment_detail view
@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(
        AssetAssignment.objects.select_related("asset", "issued_by"),
        pk=pk,
    )
    return render(request, "assets/assignment_detail.html", {"assignment": assignment})
# End assignment_detail view


# Begin assignment_create view
@login_required
@admin_or_technician_required
def assignment_create(request):
    initial = {}
    asset_id = request.GET.get("asset")
    if asset_id and Asset.objects.filter(pk=asset_id).exists():
        initial["asset"] = asset_id

    if request.method == "POST":
        form = AssetAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            assignment = form.save()
            messages.success(
                request,
                f"Assignment for {assignment.asset.asset_tag} created successfully.",
            )
            return redirect("assets:assignment_detail", pk=assignment.pk)
    else:
        form = AssetAssignmentForm(initial=initial, user=request.user)

    return render(
        request,
        "assets/assignment_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Assignment",
        },
    )
# End assignment_create view


# Begin assignment_update view
@login_required
@admin_or_technician_required
def assignment_update(request, pk):
    assignment = get_object_or_404(AssetAssignment, pk=pk)
    if request.method == "POST":
        form = AssetAssignmentForm(request.POST, instance=assignment, user=request.user)
        if form.is_valid():
            assignment = form.save()
            messages.success(
                request,
                f"Assignment for {assignment.asset.asset_tag} updated successfully.",
            )
            return redirect("assets:assignment_detail", pk=assignment.pk)
    else:
        form = AssetAssignmentForm(instance=assignment, user=request.user)

    return render(
        request,
        "assets/assignment_form.html",
        {
            "form": form,
            "assignment": assignment,
            "action": "Update",
            "page_title": f"Update Assignment for {assignment.asset.asset_tag}",
        },
    )
# End assignment_update view


# Begin assignment_delete view
@login_required
@admin_or_technician_required
@require_http_methods(["GET", "POST"])
def assignment_delete(request, pk):
    assignment = get_object_or_404(
        AssetAssignment.objects.select_related("asset", "issued_by"),
        pk=pk,
    )
    if request.method == "POST":
        asset_tag = assignment.asset.asset_tag
        assignment.delete()
        messages.success(request, f"Assignment for {asset_tag} deleted successfully.")
        return redirect("assets:assignment_list")

    return render(
        request,
        "assets/assignment_confirm_delete.html",
        {"assignment": assignment},
    )
# End assignment_delete view


# Begin maintenance_list view
@login_required
def maintenance_list(request):
    records = MaintenanceRecord.objects.select_related("asset")
    stats_queryset = MaintenanceRecord.objects.all()
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    maintenance_type = request.GET.get("maintenance_type", "").strip()
    asset_id = request.GET.get("asset", "").strip()
    selected_asset = None

    if asset_id:
        selected_asset = Asset.objects.filter(pk=asset_id).first()
        if selected_asset:
            records = records.filter(asset=selected_asset)
            stats_queryset = stats_queryset.filter(asset=selected_asset)

    if search:
        records = records.filter(
            Q(asset__asset_tag__icontains=search)
            | Q(asset__name__icontains=search)
            | Q(issue_description__icontains=search)
            | Q(technician__icontains=search)
            | Q(notes__icontains=search)
        )

    if status:
        records = records.filter(status=status)

    if maintenance_type:
        records = records.filter(maintenance_type=maintenance_type)

    paginator = Paginator(records.order_by("-start_date", "-id"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "search": search,
        "status": status,
        "maintenance_type": maintenance_type,
        "selected_asset": selected_asset,
        "filter_querystring": filter_querystring,
        "maintenance_type_choices": MaintenanceRecord.TYPE_CHOICES,
        "status_choices": MaintenanceRecord.STATUS_CHOICES,
        "stats": {
            "total": stats_queryset.count(),
            "open": stats_queryset.filter(status=MaintenanceRecord.STATUS_OPEN).count(),
            "in_progress": stats_queryset.filter(status=MaintenanceRecord.STATUS_IN_PROGRESS).count(),
            "completed": stats_queryset.filter(status=MaintenanceRecord.STATUS_COMPLETED).count(),
        },
    }
    return render(request, "assets/maintenance_list.html", context)
# End maintenance_list view


# Begin maintenance_detail view
@login_required
def maintenance_detail(request, pk):
    record = get_object_or_404(
        MaintenanceRecord.objects.select_related("asset"),
        pk=pk,
    )
    return render(request, "assets/maintenance_detail.html", {"record": record})
# End maintenance_detail view


# Begin maintenance_create view
@login_required
@admin_or_technician_required
def maintenance_create(request):
    initial = {}
    asset_id = request.GET.get("asset")
    if asset_id and Asset.objects.filter(pk=asset_id).exists():
        initial["asset"] = asset_id

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, user=request.user)
        if form.is_valid():
            record = form.save()
            messages.success(
                request,
                f"Maintenance record for {record.asset.asset_tag} created successfully.",
            )
            return redirect("assets:maintenance_detail", pk=record.pk)
    else:
        form = MaintenanceRecordForm(initial=initial, user=request.user)

    return render(
        request,
        "assets/maintenance_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Maintenance Record",
        },
    )
# End maintenance_create view


# Begin maintenance_update view
@login_required
@admin_or_technician_required
def maintenance_update(request, pk):
    record = get_object_or_404(MaintenanceRecord, pk=pk)
    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, instance=record, user=request.user)
        if form.is_valid():
            record = form.save()
            messages.success(
                request,
                f"Maintenance record for {record.asset.asset_tag} updated successfully.",
            )
            return redirect("assets:maintenance_detail", pk=record.pk)
    else:
        form = MaintenanceRecordForm(instance=record, user=request.user)

    return render(
        request,
        "assets/maintenance_form.html",
        {
            "form": form,
            "record": record,
            "action": "Update",
            "page_title": f"Update Maintenance for {record.asset.asset_tag}",
        },
    )
# End maintenance_update view


# Begin maintenance_delete view
@login_required
@admin_or_technician_required
@require_http_methods(["GET", "POST"])
def maintenance_delete(request, pk):
    record = get_object_or_404(
        MaintenanceRecord.objects.select_related("asset"),
        pk=pk,
    )
    if request.method == "POST":
        asset_tag = record.asset.asset_tag
        record.delete()
        messages.success(request, f"Maintenance record for {asset_tag} deleted successfully.")
        return redirect("assets:maintenance_list")

    return render(
        request,
        "assets/maintenance_confirm_delete.html",
        {"record": record},
    )
# End maintenance_delete view
