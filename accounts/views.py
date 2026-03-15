from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from core.decorators import admin_required

from .forms import DepartmentForm, UserCreateForm, UserUpdateForm
from .models import Department, User


# Begin user_list view
@login_required
@admin_required
def user_list(request):
    users = User.objects.select_related("department")
    search = request.GET.get("search", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()

    if search:
        users = users.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(department__name__icontains=search)
            | Q(department__code__icontains=search)
        )

    if role:
        users = users.filter(role=role)

    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    paginator = Paginator(users.order_by("-date_joined"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "search": search,
        "selected_role": role,
        "selected_status": status,
        "role_choices": User.ROLE_CHOICES,
        "filter_querystring": filter_querystring,
        "stats": {
            "total": User.objects.count(),
            "active": User.objects.filter(is_active=True).count(),
            "admins": User.objects.filter(role="ADMIN").count(),
            "technicians": User.objects.filter(role="TECHNICIAN").count(),
        },
    }
    return render(request, "accounts/user_list.html", context)


# End user_list view


# Begin user_detail view
@login_required
@admin_required
def user_detail(request, pk):
    managed_user = get_object_or_404(User.objects.select_related("department"), pk=pk)
    return render(request, "accounts/user_detail.html", {"managed_user": managed_user})


# End user_detail view


# Begin user_create view
@login_required
@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            managed_user = form.save()
            messages.success(request, f"User {managed_user.email} created successfully.")
            return redirect("accounts:user_detail", pk=managed_user.pk)
    else:
        form = UserCreateForm(initial={"is_active": True})

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create User",
        },
    )


# End user_create view


# Begin user_update view
@login_required
@admin_required
def user_update(request, pk):
    managed_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=managed_user)
        if form.is_valid():
            managed_user = form.save()
            messages.success(request, f"User {managed_user.email} updated successfully.")
            return redirect("accounts:user_detail", pk=managed_user.pk)
    else:
        form = UserUpdateForm(instance=managed_user)

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "managed_user": managed_user,
            "action": "Update",
            "page_title": f"Update {managed_user.email}",
        },
    )


# End user_update view


# Begin user_delete view
@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def user_delete(request, pk):
    managed_user = get_object_or_404(User.objects.select_related("department"), pk=pk)

    if managed_user.pk == request.user.pk:
        messages.error(request, "You cannot delete the account you are currently using.")
        return redirect("accounts:user_detail", pk=managed_user.pk)

    if request.method == "POST":
        managed_user_email = managed_user.email
        managed_user.delete()
        messages.success(request, f"User {managed_user_email} deleted successfully.")
        return redirect("accounts:user_list")

    return render(
        request,
        "accounts/user_confirm_delete.html",
        {"managed_user": managed_user},
    )


# End user_delete view


# Begin department_list view
@login_required
@admin_required
def department_list(request):
    departments = Department.objects.annotate(
        user_count=Count("users", distinct=True),
        asset_count=Count("assets", distinct=True),
    )
    search = request.GET.get("search", "").strip()

    if search:
        departments = departments.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(description__icontains=search)
        )

    paginator = Paginator(departments.order_by("name"), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "search": search,
        "filter_querystring": filter_querystring,
        "stats": {
            "total": Department.objects.count(),
            "with_users": Department.objects.filter(users__isnull=False).distinct().count(),
            "with_assets": Department.objects.filter(assets__isnull=False).distinct().count(),
        },
    }
    return render(request, "accounts/department_list.html", context)


# End department_list view


# Begin department_detail view
@login_required
@admin_required
def department_detail(request, pk):
    department = get_object_or_404(
        Department.objects.annotate(
            user_count=Count("users", distinct=True),
            asset_count=Count("assets", distinct=True),
        ),
        pk=pk,
    )
    context = {
        "department": department,
        "users": department.users.order_by("-date_joined")[:10],
        "assets": department.assets.select_related("category", "asset_type").order_by("asset_tag")[:10],
    }
    return render(request, "accounts/department_detail.html", context)


# End department_detail view


# Begin department_create view
@login_required
@admin_required
def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save()
            messages.success(request, f"Department {department.code} created successfully.")
            return redirect("accounts:department_detail", pk=department.pk)
    else:
        form = DepartmentForm()

    return render(
        request,
        "accounts/department_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Department",
        },
    )


# End department_create view


# Begin department_update view
@login_required
@admin_required
def department_update(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save()
            messages.success(request, f"Department {department.code} updated successfully.")
            return redirect("accounts:department_detail", pk=department.pk)
    else:
        form = DepartmentForm(instance=department)

    return render(
        request,
        "accounts/department_form.html",
        {
            "form": form,
            "department": department,
            "action": "Update",
            "page_title": f"Update {department.code}",
        },
    )


# End department_update view


# Begin department_delete view
@login_required
@admin_required
@require_http_methods(["GET", "POST"])
def department_delete(request, pk):
    department = get_object_or_404(
        Department.objects.annotate(
            user_count=Count("users", distinct=True),
            asset_count=Count("assets", distinct=True),
        ),
        pk=pk,
    )

    if request.method == "POST":
        department_code = department.code
        department.delete()
        messages.success(request, f"Department {department_code} deleted successfully.")
        return redirect("accounts:department_list")

    return render(
        request,
        "accounts/department_confirm_delete.html",
        {"department": department},
    )


# End department_delete view
