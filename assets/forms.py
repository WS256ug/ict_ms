from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from accounts.models import Department

from .models import (
    Asset,
    AssetAssignment,
    AssetAttributeValue,
    AssetCategory,
    AssetDepreciation,
    AssetLocationHistory,
    AssetPurchase,
    AssetType,
    Location,
    MaintenanceRecord,
)


class AssetForm(forms.ModelForm):
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        required=False,
        empty_label="Select location",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    useful_life_years = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Useful life in years"}
        ),
    )
    salvage_value = forms.DecimalField(
        required=False,
        min_value=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Salvage value", "step": "0.01"}
        ),
    )
    depreciation_start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = Asset
        fields = [
            "asset_tag",
            "name",
            "category",
            "asset_type",
            "serial_number",
            "department",
            "purchase",
            "purchase_date",
            "purchase_cost",
            "warranty_expiry",
            "status",
            "is_active",
        ]
        widgets = {
            "asset_tag": forms.TextInput(attrs={"class": "form-control", "placeholder": "Asset tag"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Asset name"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "asset_type": forms.Select(attrs={"class": "form-select"}),
            "serial_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Serial number"}
            ),
            "department": forms.Select(attrs={"class": "form-select"}),
            "purchase": forms.Select(attrs={"class": "form-select"}),
            "purchase_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "purchase_cost": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Purchase cost", "step": "0.01"}
            ),
            "warranty_expiry": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.depreciation_instance = None
        self.fields["category"].queryset = AssetCategory.objects.ordered_choices()
        self.fields["asset_type"].queryset = AssetType.objects.none()
        self.fields["asset_type"].empty_label = "Select asset type"
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["location"].queryset = Location.objects.order_by("name", "building", "room")
        self.fields["purchase"].queryset = AssetPurchase.objects.select_related("supplier").order_by(
            "-purchase_date", "-id"
        )
        self.fields["useful_life_years"].help_text = (
            "Straight-line depreciation is calculated automatically using the asset purchase cost."
        )
        current_location = self.instance.current_location if self.instance.pk else None

        if current_location and not self.is_bound:
            self.fields["location"].initial = current_location.pk

        if self.instance.pk:
            try:
                self.depreciation_instance = self.instance.depreciation
            except AssetDepreciation.DoesNotExist:
                self.depreciation_instance = None

        if self.depreciation_instance:
            self.fields["useful_life_years"].initial = self.depreciation_instance.useful_life_years
            self.fields["salvage_value"].initial = self.depreciation_instance.salvage_value
            self.fields["depreciation_start_date"].initial = self.depreciation_instance.start_date
        elif self.instance.pk:
            if self.instance.purchase_cost is not None:
                self.fields["useful_life_years"].initial = 5
                self.fields["salvage_value"].initial = Decimal("0.00")
            if self.instance.purchase_date:
                self.fields["depreciation_start_date"].initial = self.instance.purchase_date

        category_id = None
        if self.is_bound:
            category_id = self.data.get("category")
        elif self.instance.pk:
            category_id = self.instance.category_id

        if category_id:
            self.fields["asset_type"].queryset = AssetType.objects.filter(
                category_id=category_id
            ).order_by("name")
        elif self.instance.pk:
            self.fields["asset_type"].queryset = AssetType.objects.select_related("category").order_by(
                "category__name",
                "name",
            )

        if not category_id:
            self.fields["asset_type"].widget.attrs["disabled"] = "disabled"

    def clean_asset_tag(self):
        asset_tag = self.cleaned_data.get("asset_tag")
        if not asset_tag:
            return asset_tag

        queryset = Asset.objects.filter(asset_tag=asset_tag)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError("Asset tag already exists.")
        return asset_tag

    def clean(self):
        cleaned_data = super().clean()
        purchase_cost = cleaned_data.get("purchase_cost")
        purchase_date = cleaned_data.get("purchase_date")
        useful_life_years = cleaned_data.get("useful_life_years")
        salvage_value = cleaned_data.get("salvage_value")
        depreciation_start_date = cleaned_data.get("depreciation_start_date")

        if salvage_value is None:
            salvage_value = Decimal("0.00")
            cleaned_data["salvage_value"] = salvage_value

        if purchase_cost is not None and useful_life_years is None:
            useful_life_years = self.depreciation_instance.useful_life_years if self.depreciation_instance else 5
            cleaned_data["useful_life_years"] = useful_life_years

        if depreciation_start_date is None:
            depreciation_start_date = purchase_date
            cleaned_data["depreciation_start_date"] = depreciation_start_date

        has_manual_depreciation_input = any(
            value not in (None, "")
            for value in (
                cleaned_data.get("useful_life_years"),
                cleaned_data.get("depreciation_start_date"),
            )
        ) or salvage_value not in (None, Decimal("0.00"))

        should_manage_depreciation = purchase_cost is not None or has_manual_depreciation_input

        if should_manage_depreciation and purchase_cost is None:
            self.add_error("purchase_cost", "Enter the purchase cost to calculate depreciation.")

        if should_manage_depreciation and depreciation_start_date is None:
            self.add_error(
                "depreciation_start_date",
                "Enter a depreciation start date or provide the asset purchase date.",
            )

        if should_manage_depreciation and useful_life_years is None:
            self.add_error("useful_life_years", "Enter the asset useful life in years.")

        if purchase_cost is not None and salvage_value > purchase_cost:
            self.add_error("salvage_value", "Salvage value cannot exceed purchase cost.")

        return cleaned_data

    def save(self, commit=True):
        asset = super().save(commit=commit)
        if not commit:
            return asset

        purchase_cost = self.cleaned_data.get("purchase_cost")
        useful_life_years = self.cleaned_data.get("useful_life_years")
        salvage_value = self.cleaned_data.get("salvage_value") or Decimal("0.00")
        depreciation_start_date = self.cleaned_data.get("depreciation_start_date")

        if purchase_cost is not None and useful_life_years and depreciation_start_date:
            AssetDepreciation.objects.update_or_create(
                asset=asset,
                defaults={
                    "purchase_cost": purchase_cost,
                    "useful_life_years": useful_life_years,
                    "salvage_value": salvage_value,
                    "depreciation_method": AssetDepreciation.METHOD_STRAIGHT_LINE,
                    "start_date": depreciation_start_date,
                },
            )
        elif self.depreciation_instance:
            self.depreciation_instance.delete()

        selected_location = self.cleaned_data.get("location")
        current_location_record = asset.current_location_record
        current_location_id = current_location_record.location_id if current_location_record else None

        if selected_location and selected_location.pk != current_location_id:
            AssetLocationHistory.objects.create(
                asset=asset,
                location=selected_location,
                moved_by=self.user if getattr(self.user, "is_authenticated", False) else None,
                notes=(
                    "Initial location set from asset form."
                    if current_location_record is None
                    else "Location updated from asset form."
                ),
            )
        return asset


class AssetAssignmentForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = [
            "asset",
            "assignee_identifier",
            "assignee_name",
            "assignee_contact",
            "assigned_date",
            "expected_return",
            "returned_date",
            "issued_by",
            "purpose",
            "condition_at_issue",
            "condition_at_return",
            "notes",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "assignee_identifier": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "National ID, staff ID, or passport number"}
            ),
            "assignee_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full name"}
            ),
            "assignee_contact": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone number or email address"}
            ),
            "assigned_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "expected_return": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "returned_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "issued_by": forms.Select(attrs={"class": "form-select"}),
            "purpose": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Assignment purpose"}
            ),
            "condition_at_issue": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Condition when issued"}
            ),
            "condition_at_return": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Condition when returned"}
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Extra notes"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = Asset.objects.select_related(
            "category",
            "asset_type",
        ).order_by("asset_tag")
        self.fields["issued_by"].queryset = self.fields["issued_by"].queryset.order_by(
            "first_name",
            "last_name",
            "email",
        )
        self.fields["issued_by"].required = False

        if (
            self.request_user
            and getattr(self.request_user, "is_authenticated", False)
            and not self.is_bound
            and not self.instance.pk
            and not self.initial.get("issued_by")
        ):
            self.fields["issued_by"].initial = self.request_user.pk

    def clean(self):
        cleaned_data = super().clean()
        asset = cleaned_data.get("asset")
        assigned_date = cleaned_data.get("assigned_date")
        expected_return = cleaned_data.get("expected_return")
        returned_date = cleaned_data.get("returned_date")

        if assigned_date and expected_return and expected_return < assigned_date:
            self.add_error(
                "expected_return",
                "Expected return date cannot be earlier than assigned date.",
            )

        if asset and returned_date is None:
            active_assignment = AssetAssignment.objects.filter(
                asset=asset,
                returned_date__isnull=True,
            )
            if self.instance.pk:
                active_assignment = active_assignment.exclude(pk=self.instance.pk)
            if active_assignment.exists():
                self.add_error("asset", "This asset already has an active assignment.")

        return cleaned_data


class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            "asset",
            "issue_description",
            "maintenance_type",
            "start_date",
            "end_date",
            "technician",
            "cost",
            "status",
            "notes",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "issue_description": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Describe the issue or work required"}
            ),
            "maintenance_type": forms.Select(attrs={"class": "form-select"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "technician": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Technician or service provider"}
            ),
            "cost": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Maintenance cost", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Extra notes"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = Asset.objects.select_related(
            "category",
            "asset_type",
        ).order_by("asset_tag")

        if (
            self.request_user
            and getattr(self.request_user, "is_authenticated", False)
            and not self.is_bound
            and not self.instance.pk
            and not self.initial.get("technician")
        ):
            self.fields["technician"].initial = self.request_user.get_full_name()

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        end_date = cleaned_data.get("end_date")

        if status == MaintenanceRecord.STATUS_COMPLETED and not end_date:
            self.add_error("end_date", "Enter the completion date when maintenance is completed.")

        return cleaned_data


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name", "building", "room", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Location name"}),
            "building": forms.TextInput(attrs={"class": "form-control", "placeholder": "Building"}),
            "room": forms.TextInput(attrs={"class": "form-control", "placeholder": "Room"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Location description"}
            ),
        }


class AssetFilterForm(forms.Form):
    ACTIVE_CHOICES = (
        ("", "All"),
        ("true", "Active only"),
        ("false", "Inactive only"),
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by tag, name, or serial"}
        ),
    )
    category = forms.ModelChoiceField(
        queryset=AssetCategory.objects.ordered_choices(),
        required=False,
        empty_label="All categories",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    asset_type = forms.ModelChoiceField(
        queryset=AssetType.objects.select_related("category").order_by("category__name", "name"),
        required=False,
        empty_label="All asset types",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.order_by("name"),
        required=False,
        empty_label="All departments",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=(("", "All statuses"),) + tuple(Asset.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_active = forms.ChoiceField(
        choices=ACTIVE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_id = self.data.get("category") if self.is_bound else None
        if category_id:
            self.fields["asset_type"].queryset = AssetType.objects.filter(category_id=category_id).order_by(
                "name"
            )


class AssetAttributeValueForm(forms.ModelForm):
    class Meta:
        model = AssetAttributeValue
        fields = ["value"]
        widgets = {
            "value": forms.TextInput(attrs={"class": "form-control"}),
        }
