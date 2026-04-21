import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q, Sum, Prefetch
from authentication.models import UserProfile
from attendance.models import Attendance
from book_loan.models import Loan
from book.models import Book
import openpyxl
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from django.conf import settings
import os

def is_authorized(user):
    """Check if user is a teacher or librarian"""
    if user.is_superuser:
        return True
    try:
        profile = user.profile
        return profile.role in ['teacher', 'librarian']
    except UserProfile.DoesNotExist:
        return False

@login_required
def report_page_view(request):
    if not is_authorized(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman laporan.")
        return redirect('main:mainpage')
    
    return render(request, 'report/index.html')

def get_period_range(period, start_custom=None, end_custom=None):
    now = timezone.now()
    today = now.date()
    
    if period == 'custom' and start_custom and end_custom:
        try:
            start_date = datetime.strptime(start_custom, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_custom, '%Y-%m-%d').date()
            return start_date, end_date
        except (ValueError, TypeError):
            pass # Fallback to today if invalid

    if period == 'daily':
        start_date = today
        end_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:
        start_date = today
        end_date = today
        
    return start_date, end_date

def get_attendance_data(start_date, end_date):
    # Base query for attendance records in range
    records = Attendance.objects.filter(
        check_in_time__date__range=(start_date, end_date)
    ).values('check_in_time__date').annotate(
        teacher_count=Count('id', filter=Q(user__profile__role='teacher')),
        student_count=Count('id', filter=Q(user__profile__role='student')),
        total_visits=Count('id')
    ).order_by('check_in_time__date')
    
    data = []
    for r in records:
        data.append({
            'date': r['check_in_time__date'].strftime('%Y-%m-%d'),
            'teacher_count': r['teacher_count'],
            'student_count': r['student_count'],
            'total_visits': r['total_visits']
        })
    
    # Calculate summary metrics
    total_all = sum(item['total_visits'] for item in data)
    num_days = len(data) if len(data) > 0 else 1
    daily_average = round(total_all / num_days)
    
    # Busiest Day
    busiest_info = "—"
    if data:
        busiest_day_record = max(data, key=lambda x: x['total_visits'])
        busiest_date = datetime.strptime(busiest_day_record['date'], '%Y-%m-%d')
        # Map weekday to Indonesian name as per Figma
        days_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        busiest_info = days_id[busiest_date.weekday()]

    summary = {
        'total': total_all,
        'average': daily_average,
        'busiest_day': busiest_info
    }
    return data, summary

def get_borrowing_data(start_date, end_date):
    borrowed = Loan.objects.filter(loan_date__date__range=(start_date, end_date)).count()
    
    returned = Loan.objects.filter(
        return_date__date__range=(start_date, end_date),
        status='dikembalikan'
    ).count()
    
    overdue = Loan.objects.filter(
        Q(status='terlambat') | Q(is_overdue=True)
    ).filter(due_date__range=(start_date, end_date)).count()
    
    table_loans = Loan.objects.filter(
        loan_date__date__range=(start_date, end_date)
    ).select_related('user__profile', 'book').order_by('-loan_date')
    
    data = []
    for l in table_loans:
        st = l.status
        if st == 'dikembalikan':
            display_status = 'Dikembalikan'
        elif st == 'terlambat' or l.is_overdue:
            display_status = 'Terlambat'
        else:
            display_status = 'Dipinjam'
            
        data.append({
            'tanggal': l.loan_date.strftime('%d %b %Y').lstrip('0'),
            'judul_buku': l.book.title,
            'peminjam': f"{l.user.first_name} {l.user.last_name}".strip() or l.user.username,
            'kelas': getattr(l.user.profile, 'kelas', '-') if hasattr(l.user, 'profile') and l.user.profile.kelas else '-',
            'status': display_status,
            'tanggal_kembali': l.due_date.strftime('%d %b %Y').lstrip('0') if l.due_date else '-'
        })

    summary = {
        'total_dipinjam': borrowed,
        'total_dikembalikan': returned,
        'total_terlambat': overdue
    }
    return data, summary

def get_collection_data(start_date=None, end_date=None):
    # Fetch books with active loans pre-fetched to avoid N+1 queries
    active_loans_qs = Loan.objects.filter(status='sedang_dipinjam')
    books = Book.objects.all().prefetch_related(
        Prefetch('loans', queryset=active_loans_qs, to_attr='active_loans')
    )
    
    category_stats = {}
    total_physical_books = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    
    for book in books:
        # Resolve category
        raw_cat = book.category if book.category else 'Uncategorized'
        
        # Split by comma and strip whitespace
        cats = [c.strip() for c in raw_cat.split(',')]
        # Filter out empty strings
        cats = [c for c in cats if c]
        if not cats:
            cats = ['Uncategorized']
            
        # Calculate book availability stats once per book
        borrowed = len(book.active_loans)
        good_copies = book.total_copies - book.damaged_copies - book.lost_copies
        available = max(good_copies - borrowed, 0)
        
        for cat in cats:
            if cat not in category_stats:
                category_stats[cat] = {
                    'total_books': 0,
                    'tersedia': 0,
                    'dipinjam': 0
                }
            
            # Count the book's total copies and availability for EACH of its categories
            category_stats[cat]['total_books'] += book.total_copies
            category_stats[cat]['tersedia'] += available
            category_stats[cat]['dipinjam'] += borrowed
            
    # Convert aggregated dictionary back to the list format expected by the frontend
    data = []
    for cat, stats in category_stats.items():
        tot = stats['total_books']
        avl = stats['tersedia']
        brw = stats['dipinjam']
        
        persen = 0
        if tot > 0:
            persen = int((avl / tot) * 100)
            
        data.append({
            'category': cat,
            'total_books': tot,
            'tersedia': avl,
            'dipinjam': brw,
            'persentase_tersedia': f"{persen}%"
        })
        
    # Sort categories by total count descending
    data.sort(key=lambda x: x['total_books'], reverse=True)
        
    new_books_count = 0
    if start_date and end_date:
        res = Book.objects.filter(created_at__date__range=(start_date, end_date)).aggregate(Sum('total_copies'))
        new_books_count = res['total_copies__sum'] or 0

    summary = {
        'total': total_physical_books,
        'total_categories': len(category_stats),
        'new_books': new_books_count
    }
    return data, summary

@login_required
def api_report_preview(request):
    if not is_authorized(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    report_type = request.GET.get('type')
    period = request.GET.get('period')
    start_custom = request.GET.get('start_date')
    end_custom = request.GET.get('end_date')
    
    if not report_type or not period:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    start_date, end_date = get_period_range(period, start_custom, end_custom)
    
    if report_type == 'attendance':
        data, summary = get_attendance_data(start_date, end_date)
        columns = [
            {'header': 'Tanggal', 'key': 'date'},
            {'header': 'Guru', 'key': 'teacher_count'},
            {'header': 'Siswa', 'key': 'student_count'},
            {'header': 'Total Kunjungan', 'key': 'total_visits'}
        ]
    elif report_type == 'borrowing':
        data, summary = get_borrowing_data(start_date, end_date)
        columns = [
            {'header': 'TANGGAL', 'key': 'tanggal'},
            {'header': 'JUDUL BUKU', 'key': 'judul_buku'},
            {'header': 'PEMINJAM', 'key': 'peminjam'},
            {'header': 'KELAS', 'key': 'kelas'},
            {'header': 'STATUS', 'key': 'status'},
            {'header': 'TANGGAL KEMBALI', 'key': 'tanggal_kembali'}
        ]
    elif report_type == 'collection':
        data, summary = get_collection_data(start_date, end_date)
        columns = [
            {'header': 'Kategori', 'key': 'category'},
            {'header': 'Total Buku', 'key': 'total_books'},
            {'header': 'Tersedia', 'key': 'tersedia'},
            {'header': 'Dipinjam', 'key': 'dipinjam'},
            {'header': 'Persentase Tersedia', 'key': 'persentase_tersedia'}
        ]
    else:
        return JsonResponse({'error': 'Invalid report type'}, status=400)
    
    return JsonResponse({
        'status': 'success',
        'data': data,
        'summary': summary,
        'columns': columns,
        'period_label': f"{start_date} s/d {end_date}"
    })

@login_required
def api_report_export(request):
    if not is_authorized(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    report_type = request.POST.get('type')
    period = request.POST.get('period')
    export_format = request.POST.get('format')
    start_custom = request.POST.get('start_date')
    end_custom = request.POST.get('end_date')
    
    if not report_type or not period or not export_format:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    start_date, end_date = get_period_range(period, start_custom, end_custom)
    
    if report_type == 'attendance':
        data, _ = get_attendance_data(start_date, end_date)
        title = "Laporan Kehadiran Perpustakaan"
        headers = ['Tanggal', 'Guru', 'Siswa', 'Total Kunjungan']
        rows = [[item['date'], item['teacher_count'], item['student_count'], item['total_visits']] for item in data]
    elif report_type == 'borrowing':
        data, _ = get_borrowing_data(start_date, end_date)
        title = "Laporan Aktivitas Peminjaman"
        headers = ['TANGGAL', 'JUDUL BUKU', 'PEMINJAM', 'KELAS', 'STATUS', 'TANGGAL KEMBALI']
        rows = [[item['tanggal'], item['judul_buku'], item['peminjam'], item['kelas'], item['status'], item['tanggal_kembali']] for item in data]
    elif report_type == 'collection':
        data, _ = get_collection_data(start_date, end_date)
        title = "Laporan Koleksi Buku"
        headers = ['Kategori', 'Total Buku', 'Tersedia', 'Dipinjam', 'Persentase Tersedia']
        rows = [[item['category'], item['total_books'], item['tersedia'], item['dipinjam'], item['persentase_tersedia']] for item in data]
    else:
        return JsonResponse({'error': 'Invalid report type'}, status=400)

    period_str = f"{start_date} s/d {end_date}"

    # --- Summary Row Calculation (Unified for Excel and PDF) ---
    if report_type == 'attendance':
        t_guru = sum(int(row[1]) for row in rows)
        t_siswa = sum(int(row[2]) for row in rows)
        t_visits = sum(int(row[3]) for row in rows)
        rows.append(['TOTAL', t_guru, t_siswa, t_visits])
    elif report_type == 'collection':
        # Need to handle potential non-integer or percentage strings if they exist
        # Category stats in collection: Total, Tersedia, Dipinjam are indices 1,2,3
        t_books = sum(int(row[1]) for row in rows)
        t_avl = sum(int(row[2]) for row in rows)
        t_brw = sum(int(row[3]) for row in rows)
        rows.append(['TOTAL', t_books, t_avl, t_brw, '-'])

    if export_format == 'excel':
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report"
        
        num_cols = len(headers)
        
        # --- Formal Letterhead ---
        text_start_col = 1
        
        # Merged Header Rows
        def add_merge_header(row, text, size, bold=True):
            ws.merge_cells(start_row=row, start_column=text_start_col, end_row=row, end_column=num_cols)
            cell = ws.cell(row=row, column=text_start_col)
            cell.value = text
            cell.font = Font(name='Arial', size=size, bold=bold)
            cell.alignment = Alignment(horizontal='center')

        add_merge_header(1, "PEMERINTAH PROVINSI D.K.I JAKARTA", 12)
        add_merge_header(2, "SMA NEGERI 61 JAKARTA", 14)
        add_merge_header(3, "Jl. Taruna Jl. Pahlawan Revolusi, Pd. Bambu, Kec. Duren Sawit, Jakarta Timur", 10, False)
        
        # Report Title Row
        ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=num_cols)
        ws['A5'] = title.upper()
        ws['A5'].font = Font(name='Arial', size=14, bold=True)
        ws['A5'].alignment = Alignment(horizontal='center')
        
        ws.append([]) # spacer
        ws.append([f"Periode: {period_str}"])
        ws.append([f"Tanggal Cetak: {datetime.now().strftime('%d %B %Y %H:%M:%S')}"])
        ws.append([]) # spacer
        
        # Table Headers
        header_row_idx = ws.max_row + 1
        ws.append(headers)
        
        header_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
        header_font = Font(bold=True)
        header_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        
        for cell in ws[header_row_idx]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = header_border
            
        # Data
        for row in rows:
            ws.append(row)
            
        # Borders and Total Row Styling
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        for r_idx in range(header_row_idx + 1, ws.max_row + 1):
            is_total = (ws.cell(row=r_idx, column=1).value == 'TOTAL')
            for cell in ws[r_idx]:
                cell.border = thin_border
                if is_total:
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        # Auto-adjust column widths
        for col_idx, col in enumerate(ws.columns, 1):
            max_length = 0
            column_letter = get_column_letter(col_idx)
            for cell in col:
                try:
                    # MergedCells have no value, so we only measure normal cells
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 5) * 1.1
            ws.column_dimensions[column_letter].width = min(adjusted_width, 50) # Cap width at 50

        output = BytesIO()
        wb.save(output)
        
        filename = f"report_{report_type}_{period}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    elif export_format == 'pdf':
        buffer = BytesIO()
        
        # --- Total Page Numbering Logic ---
        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                canvas.Canvas.__init__(self, *args, **kwargs)
                self.pages = []

            def showPage(self):
                self.pages.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                page_count = len(self.pages)
                for page in self.pages:
                    self.__dict__.update(page)
                    self.draw_page_number(page_count)
                    canvas.Canvas.showPage(self)
                canvas.Canvas.save(self)

            def draw_page_number(self, page_count):
                self.setFont("Times-Roman", 10)
                self.drawRightString(200 * mm, 15 * mm, f"Halaman {self._pageNumber} dari {page_count}")
        
        # Class for page numbering
        
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=30*mm)
        elements = []
        styles = getSampleStyleSheet()
        
        # Formal Styles
        title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Times-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=2)
        address_style = ParagraphStyle('AddressStyle', parent=styles['Normal'], fontName='Times-Roman', fontSize=10, alignment=TA_CENTER, spaceAfter=2)
        report_title_style = ParagraphStyle('ReportTitle', parent=styles['Normal'], fontName='Times-Bold', fontSize=16, alignment=TA_CENTER, spaceBefore=20, spaceAfter=25)
        info_style = ParagraphStyle('InfoStyle', parent=styles['Normal'], fontName='Times-Roman', fontSize=11, spaceAfter=4)

        # --- Kop Surat (Letterhead) ---
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'assets', 'logoSMAN61.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=25*mm, height=25*mm)
        else:
            img = Paragraph("", styles['Normal'])

        header_text = [
            Paragraph("PEMERINTAH PROVINSI D.K.I JAKARTA", title_style),
            Paragraph("SMA NEGERI 61 JAKARTA", ParagraphStyle('SchoolName', parent=title_style, fontSize=16, spaceBefore=4, spaceAfter=8)),
            Paragraph("Jl. Taruna Jl. Pahlawan Revolusi, Pd. Bambu, Kec. Duren Sawit, Kota Jakarta Timur", address_style),
            Paragraph("Daerah Khusus Ibukota Jakarta 13430", address_style),
        ]

        header_table_data = [[img, header_text]]
        header_table = Table(header_table_data, colWidths=[30*mm, 140*mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
        ]))
        elements.append(header_table)
        
        # Horizontal line separator
        from reportlab.platypus import HRFlowable
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceBefore=5, spaceAfter=1))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceBefore=1, spaceAfter=10))

        # Report Header
        elements.append(Paragraph(title.upper(), report_title_style))
        elements.append(Paragraph(f"Periode: {period_str}", info_style))
        elements.append(Paragraph(f"Tanggal Cetak: {datetime.now().strftime('%d %B %Y %H:%M:%S')}", info_style))
        elements.append(Spacer(1, 10))

        # --- Table Implementation ---
        table_data = [headers] + rows
        
        # Adjusted col widths based on report type
        if report_type == 'collection':
            col_widths = [60*mm, 25*mm, 25*mm, 25*mm, 35*mm]
        elif report_type == 'attendance':
            col_widths = [40*mm, 40*mm, 40*mm, 50*mm]
        else:
            col_widths = None # Auto

        t = Table(table_data, repeatRows=1, colWidths=col_widths)
        
        table_style = [
            ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Heading Style
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
        ]
        
        # Add bold style to the TOTAL row if it exists
        if report_type in ['attendance', 'collection']:
            last_row_idx = len(table_data) - 1
            table_style.append(('FONTNAME', (0, last_row_idx), (-1, last_row_idx), 'Times-Bold'))
            table_style.append(('BACKGROUND', (0, last_row_idx), (-1, last_row_idx), colors.lightgrey))

        # Alignment for borrowing status column
        if report_type == 'borrowing':
            table_style.append(('ALIGN', (4, 1), (4, -1), 'CENTER'))

        t.setStyle(TableStyle(table_style))
        elements.append(t)
        
        # Build document with page numbering
        doc.build(elements, canvasmaker=NumberedCanvas)
        
        filename = f"report_{report_type}_{period}_{datetime.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return JsonResponse({'error': 'Invalid format'}, status=400)
