from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.db.models import Q
from .models import FaultTicket, TicketComment, TicketAttachment


class TicketCommentInline(admin.TabularInline):
    """
    Inline display of ticket comments
    """
    model = TicketComment
    extra = 1
    readonly_fields = ('user', 'created_at')
    fields = ('user', 'comment', 'created_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')


class TicketAttachmentInline(admin.TabularInline):
    """
    Inline display of ticket attachments
    """
    model = TicketAttachment
    extra = 1
    readonly_fields = ('uploaded_by', 'uploaded_at')
    fields = ('file', 'description', 'uploaded_by', 'uploaded_at')


@admin.register(FaultTicket)
class FaultTicketAdmin(admin.ModelAdmin):
    """
    Customized admin for fault ticket management
    """
    list_display = (
        'ticket_id',
        'title',
        'department',
        'asset',
        'priority_badge',
        'status_badge',
        'reported_by',
        'assigned_to',
        'overdue_indicator',
        'created_at'
    )
    
    list_filter = (
        'status',
        'priority',
        'department',
        'created_at',
        'assigned_to'
    )
    
    search_fields = (
        'ticket_id',
        'title',
        'description',
        'reported_by__email',
        'assigned_to__email'
    )
    
    readonly_fields = (
        'ticket_id',
        'created_at',
        'updated_at',
        'assigned_at',
        'resolved_at',
        'closed_at',
        'resolution_time_display',
        'overdue_indicator'
    )
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'title', 'description', 'asset', 'department')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Assignment', {
            'fields': ('reported_by', 'assigned_to')
        }),
        ('Resolution', {
            'fields': ('resolution_notes',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 
                'assigned_at', 
                'resolved_at', 
                'closed_at',
                'updated_at',
                'resolution_time_display'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TicketCommentInline, TicketAttachmentInline]
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    actions = ['assign_to_me', 'mark_in_progress', 'mark_resolved']
    
    def priority_badge(self, obj):
        """Color-coded priority badge"""
        colors = {
            'LOW': '#6c757d',
            'MEDIUM': '#ffc107',
            'HIGH': '#fd7e14',
            'CRITICAL': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        """Color-coded status badge"""
        colors = {
            'OPEN': '#17a2b8',
            'ASSIGNED': '#007bff',
            'IN_PROGRESS': '#ffc107',
            'RESOLVED': '#28a745',
            'CLOSED': '#6c757d',
            'CANCELLED': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def overdue_indicator(self, obj):
        """Show overdue warning"""
        if obj.is_overdue:
            return format_html(
                '<span style="color: {}; font-weight: bold;">&#9888; {}</span>',
                'red',
                'OVERDUE'
            )
        return format_html(
            '<span style="color: {};">&#10003; {}</span>',
            'green',
            'On Track'
        )
    overdue_indicator.short_description = 'SLA Status'
    
    def resolution_time_display(self, obj):
        """Display time taken to resolve"""
        if obj.resolution_time:
            total_seconds = obj.resolution_time.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        return "Not resolved yet"
    resolution_time_display.short_description = 'Resolution Time'
    
    # Custom actions
    def assign_to_me(self, request, queryset):
        """Assign selected tickets to current user"""
        updated = queryset.filter(
            Q(status='OPEN') | Q(status='ASSIGNED')
        ).update(assigned_to=request.user, status='ASSIGNED')
        self.message_user(request, f'{updated} tickets assigned to you.')
    assign_to_me.short_description = 'Assign selected tickets to me'
    
    def mark_in_progress(self, request, queryset):
        """Mark tickets as in progress"""
        updated = queryset.filter(status__in=['OPEN', 'ASSIGNED']).update(status='IN_PROGRESS')
        self.message_user(request, f'{updated} tickets marked as In Progress.')
    mark_in_progress.short_description = 'Mark as In Progress'
    
    def mark_resolved(self, request, queryset):
        """Mark tickets as resolved"""
        from django.utils import timezone
        updated = 0
        for ticket in queryset.filter(status__in=['IN_PROGRESS', 'ASSIGNED']):
            ticket.status = 'RESOLVED'
            ticket.resolved_at = timezone.now()
            ticket.save()
            updated += 1
        self.message_user(request, f'{updated} tickets marked as Resolved.')
    mark_resolved.short_description = 'Mark as Resolved'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('department', 'asset', 'reported_by', 'assigned_to')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit assigned_to field to only technicians and admins"""
        if db_field.name == "assigned_to":
            user_model = get_user_model()
            kwargs["queryset"] = user_model.objects.filter(
                Q(role='TECHNICIAN') | Q(role='ADMIN')
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

