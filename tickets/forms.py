from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.models import Department
from assets.models import Asset, Location

from .models import FaultTicket, TicketAttachment, TicketComment, TicketResolution


User = get_user_model()
WORKFLOW_ASSIGNABLE_ROLES = ["ADMIN", "HELP_DESK", "TECHNICIAN"]


class BaseTicketForm(forms.ModelForm):
    class Meta:
        model = FaultTicket
        fields = [
            "title",
            "description",
            "department",
            "ticket_category",
            "is_asset_fault",
            "asset",
            "location",
            "priority",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Short summary of the issue"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Describe the fault, symptoms, and any troubleshooting already done",
                }
            ),
            "department": forms.Select(attrs={"class": "form-select"}),
            "ticket_category": forms.Select(attrs={"class": "form-select"}),
            "is_asset_fault": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "location": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["location"].queryset = Location.objects.order_by("name", "building", "room")
        self.fields["asset"].queryset = Asset.objects.none()
        self.fields["asset"].empty_label = "Select asset"
        self.fields["asset"].required = False
        self.fields["location"].required = False
        self.fields["department"].widget.attrs.update(
            {
                "hx-get": reverse("tickets:ticket_asset_field"),
                "hx-target": "#ticket-asset-field",
                "hx-trigger": "change",
                "hx-include": "#id_department, #id_asset",
            }
        )

        if self.instance.pk and not self.is_bound and not self.instance.location_id and self.instance.asset_id:
            self.fields["location"].initial = getattr(self.instance.asset.current_location, "pk", None)

        if (
            self.user
            and getattr(self.user, "is_authenticated", False)
            and getattr(self.user, "is_department_user", False)
            and self.user.department_id
        ):
            self.fields["department"].queryset = Department.objects.filter(pk=self.user.department_id)
            self.fields["department"].initial = self.user.department_id
            self.fields["department"].disabled = True

        department_id = None
        if self.is_bound:
            department_id = self.data.get("department")
            if (
                not department_id
                and self.user
                and getattr(self.user, "is_authenticated", False)
                and getattr(self.user, "is_department_user", False)
                and self.user.department_id
            ):
                department_id = self.user.department_id
        elif self.instance.pk and self.instance.department_id:
            department_id = self.instance.department_id
        elif (
            self.user
            and getattr(self.user, "is_authenticated", False)
            and getattr(self.user, "is_department_user", False)
            and self.user.department_id
        ):
            department_id = self.user.department_id

        if department_id:
            self.fields["asset"].queryset = Asset.objects.select_related("department").filter(
                department_id=department_id
            ).order_by("asset_tag", "name")

    def clean_department(self):
        if (
            self.user
            and getattr(self.user, "is_authenticated", False)
            and getattr(self.user, "is_department_user", False)
            and self.user.department_id
        ):
            return self.user.department
        return self.cleaned_data.get("department")

    def clean(self):
        cleaned_data = super().clean()
        asset = cleaned_data.get("asset")
        department = cleaned_data.get("department")
        location = cleaned_data.get("location")
        ticket_category = cleaned_data.get("ticket_category")
        is_asset_fault = cleaned_data.get("is_asset_fault")

        if asset and department and asset.department_id and asset.department_id != department.pk:
            self.add_error(
                "asset",
                "Selected asset belongs to a different department than the ticket.",
            )

        if ticket_category == FaultTicket.CATEGORY_HARDWARE:
            cleaned_data["is_asset_fault"] = True
            is_asset_fault = True

        if is_asset_fault and not asset:
            self.add_error("asset", "Select the affected asset for asset fault tickets.")

        if asset and not location:
            cleaned_data["location"] = asset.current_location

        return cleaned_data

    def save(self, commit=True):
        ticket = super().save(commit=False)
        if ticket.asset_id and not ticket.location_id:
            ticket.location = ticket.asset.current_location
        if commit:
            ticket.save()
        return ticket


class FaultTicketCreateForm(BaseTicketForm):
    pass


class TicketWorkflowForm(forms.ModelForm):
    class Meta:
        model = FaultTicket
        fields = [
            "status",
            "impact",
            "assigned_to",
            "due_date",
            "requires_maintenance",
            "escalated",
            "resolution_notes",
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "impact": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "requires_maintenance": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "escalated": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "resolution_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Operational notes for triage, pending states, or handoff context",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            role__in=WORKFLOW_ASSIGNABLE_ROLES
        ).order_by("first_name", "last_name", "email")
        self.fields["assigned_to"].required = False
        self.fields["resolution_notes"].required = False
        if self.instance.pk and self.instance.due_date and not self.is_bound:
            self.initial["due_date"] = self.instance.due_date.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        assigned_to = cleaned_data.get("assigned_to")
        requires_maintenance = cleaned_data.get("requires_maintenance")
        has_resolution = self.instance.pk and TicketResolution.objects.filter(ticket=self.instance).exists()

        if status in {
            FaultTicket.STATUS_ASSIGNED,
            FaultTicket.STATUS_IN_PROGRESS,
            FaultTicket.STATUS_PENDING_USER,
            FaultTicket.STATUS_PENDING_PARTS,
        } and not assigned_to:
            self.add_error("assigned_to", "Assign the ticket before moving it into an active queue.")

        if requires_maintenance and not self.instance.asset_id:
            self.add_error(
                "requires_maintenance",
                "Maintenance can only be required for asset-linked tickets.",
            )

        if status == FaultTicket.STATUS_RESOLVED and not has_resolution:
            self.add_error("status", "Use the resolution panel to mark a ticket resolved.")

        if status == FaultTicket.STATUS_CLOSED and not self.instance.resolved_at:
            self.add_error("status", "Resolve the ticket before closing it.")

        return cleaned_data

    def save(self, commit=True):
        ticket = super().save(commit=False)

        if (
            self.user
            and ticket.status != FaultTicket.STATUS_OPEN
            and not ticket.triaged_by_id
            and (
                getattr(self.user, "is_admin", False)
                or getattr(self.user, "is_help_desk", False)
            )
        ):
            ticket.triaged_by = self.user

        if ticket.assigned_to_id and ticket.status in {
            FaultTicket.STATUS_OPEN,
            FaultTicket.STATUS_TRIAGED,
        }:
            ticket.status = FaultTicket.STATUS_ASSIGNED
        elif ticket.status == FaultTicket.STATUS_OPEN and ticket.triaged_by_id:
            ticket.status = FaultTicket.STATUS_TRIAGED

        if commit:
            ticket.save()
        return ticket


class TicketResolutionForm(forms.ModelForm):
    class Meta:
        model = TicketResolution
        fields = ["resolution_summary", "root_cause", "action_taken"]
        widgets = {
            "resolution_summary": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Short summary of the resolution provided to the user",
                }
            ),
            "root_cause": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Underlying cause of the incident",
                }
            ),
            "action_taken": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Steps taken to resolve the issue",
                }
            ),
        }


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Add an update, diagnosis, or response for this ticket",
                }
            )
        }


class TicketAttachmentForm(forms.ModelForm):
    class Meta:
        model = TicketAttachment
        fields = ["file", "description"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional description"}
            ),
        }


class TicketFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by ticket ID, title, requester, asset, or location",
            }
        ),
    )
    status = forms.ChoiceField(
        choices=(("", "All statuses"),) + tuple(FaultTicket.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = forms.ChoiceField(
        choices=(("", "All priorities"),) + tuple(FaultTicket.PRIORITY_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    ticket_category = forms.ChoiceField(
        choices=(("", "All categories"),) + tuple(FaultTicket.CATEGORY_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.order_by("name"),
        required=False,
        empty_label="All departments",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=WORKFLOW_ASSIGNABLE_ROLES).order_by(
            "first_name",
            "last_name",
            "email",
        ),
        required=False,
        empty_label="Any assignee",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    overdue_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.user = user

        if not (
            user
            and getattr(user, "is_authenticated", False)
            and (
                getattr(user, "is_admin", False)
                or getattr(user, "is_help_desk", False)
                or getattr(user, "is_management", False)
            )
        ):
            self.fields.pop("department")
            self.fields.pop("assigned_to")
