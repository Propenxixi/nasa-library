from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime

User = get_user_model()


class Loan(models.Model):
    STATUS_CHOICES = [
        ('menunggu_konfirmasi', 'Menunggu Konfirmasi'),
        ('siap_diambil', 'Siap Diambil'),
        ('sedang_dipinjam', 'Sedang Dipinjam'),
        ('menunggu_persetujuan_perpanjangan', 'Menunggu Persetujuan Perpanjangan'),
        ('terlambat', 'Terlambat'),
        ('dikembalikan', 'Dikembalikan'),
        ('ditolak', 'Ditolak'),
    ]

    BOOK_CONDITION_CHOICES = [
        ('baik', 'Baik'),
        ('rusak', 'Rusak'),
        ('hilang', 'Hilang'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    book = models.ForeignKey('book.Book', on_delete=models.CASCADE, related_name='loans')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='menunggu_konfirmasi')
    
    # Dates
    loan_date = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    
    # Duration
    duration_days = models.PositiveIntegerField(default=7)
    
    # Return condition
    return_condition = models.CharField(
        max_length=20,
        choices=BOOK_CONDITION_CHOICES,
        null=True,
        blank=True
    )
    
    # Rejection / Return notes
    rejection_reason = models.TextField(blank=True, null=True)
    return_notes = models.TextField(blank=True, null=True)
    
    # Flag for late return
    is_overdue = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-loan_date']

    def __str__(self):
        return f"{self.user.first_name} - {self.book.title} ({self.get_status_display()})"

    @property
    def days_overdue(self):
        """Calculate days overdue if applicable"""
        if self.due_date and self.status == 'sedang_dipinjam':
            overdue = (timezone.now().date() - self.due_date).days
            return max(overdue, 0)
        return 0

    @property
    def can_extend(self):
        """Check if loan can be extended"""
        if self.status != 'sedang_dipinjam':
            return False
        if self.due_date and self.due_date < timezone.now().date():
            return False
        return True

    def approve(self):
        """Approve the loan - book becomes ready to pick up"""
        self.status = 'siap_diambil'
        self.approved_date = timezone.now()
        self.due_date = (timezone.now() + timedelta(days=self.duration_days)).date()
        # Stock will be decreased when book is actually picked up
        self.save()

    def pickup(self):
        """Student picks up the book - mark as borrowed"""
        self.status = 'sedang_dipinjam'
        self.save()
        
        # Update book status based on available copies (property calculates this)
        if self.book.available_copies <= 0:
            self.book.status = 'tidak_tersedia'
        else:
            self.book.status = 'tersedia'
        self.book.save()

    def reject(self, reason=''):
        """Reject the loan"""
        self.status = 'ditolak'
        self.rejection_reason = reason
        self.save()

    def process_return(self, condition):
        """Process book return - tracks condition of returned copy"""
        self.status = 'dikembalikan'
        self.return_date = timezone.now()
        self.return_condition = condition
        self.save()
        
        # Update book copy condition counters (not the entire book status)
        if condition == 'rusak':
            # Increment damaged counter
            self.book.damaged_copies += 1
        elif condition == 'hilang':
            # Increment lost counter
            self.book.lost_copies += 1
        # If 'baik', no counter changes needed, just mark as returned
        
        # Update book status based on good copies availability
        good_copies = self.book.total_copies - self.book.damaged_copies - self.book.lost_copies
        if good_copies > 0:
            self.book.status = 'tersedia'
        else:
            self.book.status = 'tidak_tersedia'
        
        self.book.save()
        
        # PBI backlog: Distribute to waiting list when book becomes available
        if good_copies > 0:
            self.book.distribute_waiting_list()


class LoanExtension(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu Persetujuan'),
        ('approved', 'Disetujui'),
        ('rejected', 'Ditolak'),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='extensions')
    requested_duration = models.PositiveIntegerField(default=7)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    requested_date = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    new_due_date = models.DateField(null=True, blank=True)
    
    rejection_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-requested_date']

    def __str__(self):
        return f"Extension {self.loan.id} - {self.get_status_display()}"

    def approve(self):
        """Approve extension request"""
        self.status = 'approved'
        self.approved_date = timezone.now()
        self.new_due_date = (self.loan.due_date + timedelta(days=self.requested_duration))
        
        self.loan.status = 'sedang_dipinjam'
        self.loan.due_date = self.new_due_date
        self.loan.save()
        
        self.save()

    def reject(self, reason=''):
        """Reject extension request"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.loan.status = 'sedang_dipinjam'
        self.loan.save()
        self.save()


class WaitingList(models.Model):
    STATUS_CHOICES = [
        ('menunggu', 'Menunggu'),
        ('siap_dipinjam', 'Siap Dipinjam'),
        ('dibatalkan', 'Dibatalkan'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='waiting_lists')
    book = models.ForeignKey('book.Book', on_delete=models.CASCADE, related_name='waiting_lists')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    
    position = models.PositiveIntegerField()
    registered_date = models.DateTimeField(auto_now_add=True)
    
    ready_date = models.DateTimeField(null=True, blank=True)
    claim_deadline = models.DateTimeField(null=True, blank=True)
    is_claimed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['position', 'registered_date']
        unique_together = ('user', 'book')

    def __str__(self):
        return f"{self.user.first_name} - {self.book.title} (Position #{self.position})"

    @property
    def is_expired(self):
        """Check if claim deadline has passed"""
        if self.claim_deadline and self.status == 'siap_dipinjam' and not self.is_claimed:
            return timezone.now() > self.claim_deadline
        return False

    def mark_ready(self):
        """Mark as ready to be claimed"""
        self.status = 'siap_dipinjam'
        self.ready_date = timezone.now()
        self.claim_deadline = timezone.now() + timedelta(hours=24)
        self.save()

    def claim(self):
        """Mark as claimed"""
        self.is_claimed = True
        self.save()

    def cancel(self):
        """Cancel from waiting list"""
        self.status = 'dibatalkan'
        self.save()


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('reminder_due', 'Reminder Jatuh Tempo'),
        ('extension_approved', 'Perpanjangan Disetujui'),
        ('extension_rejected', 'Perpanjangan Ditolak'),
        ('waitlist_ready', 'Antrian Siap Dipinjam'),
        ('loan_approved', 'Peminjaman Disetujui'),
        ('loan_rejected', 'Peminjaman Ditolak'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    book = models.ForeignKey('book.Book', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.first_name} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
