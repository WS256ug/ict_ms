from django.db import models
from django.conf import settings
from accounts.models import Department
from assets.models import Asset
from django.utils import timezone
import random
import string

def generate_ticket_id():
    """Generate unique ticket ID (e.g., TKT-2025-ABC123)"""
    year = timezone.now().year
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TKT-{year}-{random_part}"


class FaultTicket(models.Model):
    """
    Fault reporting and ticketing system
    """
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ASSIGNED', 'Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    ticket_id = models.CharField(max_length=50, unique=True, default=generate_ticket_id, editable=False)
    title = models.CharField(max_length=300)
    description = models.TextField()
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='tickets', null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='tickets')
    
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reported_tickets')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    resolution_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fault Ticket'
        verbose_name_plural = 'Fault Tickets'
        indexes = [
            models.Index(fields=['ticket_id']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.title}"
    
    @property
    def resolution_time(self):
        """Calculate time taken to resolve ticket"""
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None
    
    @property
    def is_overdue(self):
        """Check if ticket is overdue (open > 48 hours for HIGH/CRITICAL)"""
        if self.status in ['RESOLVED', 'CLOSED', 'CANCELLED']:
            return False
        
        if self.priority in ['HIGH', 'CRITICAL']:
            time_elapsed = timezone.now() - self.created_at
            return time_elapsed.total_seconds() > 48 * 3600  # 48 hours
        return False
    
    def save(self, *args, **kwargs):
        # Auto-update timestamps based on status changes
        if self.pk:  # Only for existing tickets
            old_ticket = FaultTicket.objects.get(pk=self.pk)
            
            if old_ticket.status != self.status:
                if self.status == 'ASSIGNED' and not self.assigned_at:
                    self.assigned_at = timezone.now()
                elif self.status == 'RESOLVED' and not self.resolved_at:
                    self.resolved_at = timezone.now()
                elif self.status == 'CLOSED' and not self.closed_at:
                    self.closed_at = timezone.now()
        
        super().save(*args, **kwargs)


class TicketComment(models.Model):
    """
    Comments/updates on fault tickets
    """
    ticket = models.ForeignKey(FaultTicket, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Ticket Comment'
        verbose_name_plural = 'Ticket Comments'
    
    def __str__(self):
        return f"Comment on {self.ticket.ticket_id} by {self.user}"


class TicketAttachment(models.Model):
    """
    File attachments for fault tickets (photos, documents)
    """
    ticket = models.ForeignKey(FaultTicket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='tickets/attachments/')
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Ticket Attachment'
        verbose_name_plural = 'Ticket Attachments'
    
    def __str__(self):
        return f"Attachment for {self.ticket.ticket_id}"
