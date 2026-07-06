"""Servis masası web görünümleri."""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q
from django.utils.translation import gettext as _

from .helpdesk import (
    can_access_ticket, get_helpdesk_analytics, is_support_staff,
    notify_ticket_event, ensure_default_groups, ensure_default_categories,
    ROLE_ADMIN, ROLE_SUPPORT, ROLE_CUSTOMER,
)
from .models import (
    Ticket, TicketComment, TicketAttachment, TicketCategory,
    Notification, UserProfile, SystemLog,
)
from .forms import (
    TicketForm, TicketCommentForm, TicketAttachmentForm,
    UserProfileForm, RegisterUserForm, UserEditForm,
)


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related('created_by', 'assigned_to', 'device', 'ticket_category'),
        pk=pk,
    )
    if not can_access_ticket(request.user, ticket):
        messages.error(request, _('Bu talebe erişim yetkiniz yok.'))
        return redirect('custom_admin' if is_support_staff(request.user) else 'user_panel')

    comments = ticket.comments.select_related('author')
    if not is_support_staff(request.user):
        comments = comments.filter(is_internal=False)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'comment':
            comment_form = TicketCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.ticket = ticket
                comment.author = request.user
                if not is_support_staff(request.user):
                    comment.is_internal = False
                comment.save()
                notify_ticket_event(ticket, 'comment', actor=request.user)
                SystemLog.objects.create(
                    user=request.user, action='TICKET',
                    details=f'#{ticket.id} talebine yorum eklendi.',
                )
                messages.success(request, _('Yorumunuz eklendi.'))
                return redirect('ticket_detail', pk=pk)

        elif action == 'attachment' and request.FILES.get('file'):
            attachment_form = TicketAttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.ticket = ticket
                attachment.uploaded_by = request.user
                attachment.save()
                messages.success(request, _('Dosya eklendi.'))
                return redirect('ticket_detail', pk=pk)

        elif action == 'update_status' and is_support_staff(request.user):
            new_status = request.POST.get('status')
            if new_status in dict(Ticket.STATUS_CHOICES):
                ticket.status = new_status
                ticket.save()
                messages.success(request, _('Talep durumu güncellendi.'))
                return redirect('ticket_detail', pk=pk)

        elif action == 'assign' and is_support_staff(request.user):
            assignee_id = request.POST.get('assigned_to')
            if assignee_id:
                ticket.assigned_to = get_object_or_404(User, pk=assignee_id)
                ticket.save()
                messages.success(request, _('Talep atandı.'))
                return redirect('ticket_detail', pk=pk)

    support_agents = User.objects.filter(
        Q(is_staff=True) | Q(groups__name__in=['Destek Personeli', 'Help Desk Ekibi', 'Ağ Ekibi', 'Sistem Ekibi'])
    ).distinct().order_by('username')

    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'attachments': ticket.attachments.select_related('uploaded_by'),
        'comment_form': TicketCommentForm(),
        'attachment_form': TicketAttachmentForm(),
        'support_agents': support_agents,
        'status_choices': Ticket.STATUS_CHOICES,
    })


@login_required
def helpdesk_analytics(request):
    if not is_support_staff(request.user):
        return redirect('dashboard')

    analytics = get_helpdesk_analytics()
    category_labels = [c['category'] for c in analytics['by_category']]
    category_counts = [c['count'] for c in analytics['by_category']]
    priority_labels = [p['priority'] for p in analytics['by_priority']]
    priority_counts = [p['count'] for p in analytics['by_priority']]
    status_labels = [s['status'] for s in analytics['by_status']]
    status_counts = [s['count'] for s in analytics['by_status']]

    return render(request, 'helpdesk_analytics.html', {
        'analytics': analytics,
        'category_labels_json': json.dumps(category_labels),
        'category_counts_json': json.dumps(category_counts),
        'priority_labels_json': json.dumps(priority_labels),
        'priority_counts_json': json.dumps(priority_counts),
        'status_labels_json': json.dumps(status_labels),
        'status_counts_json': json.dumps(status_counts),
        'recent_tickets': Ticket.objects.select_related('created_by', 'assigned_to').order_by('-created_at')[:10],
    })


@login_required
def export_tickets_csv(request):
    if not is_support_staff(request.user):
        messages.error(request, _('CSV dışa aktarma yetkiniz yok.'))
        return redirect('dashboard')

    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="talepler.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Başlık', 'Durum', 'Öncelik', 'Kategori', 'Oluşturan',
        'Atanan', 'Oluşturulma', 'SLA', 'SLA İhlali', 'Eskale',
    ])
    for t in Ticket.objects.select_related('created_by', 'assigned_to').order_by('-created_at'):
        writer.writerow([
            t.id, t.title, t.status, t.priority, t.category,
            t.created_by.username if t.created_by else '',
            t.assigned_to.username if t.assigned_to else '',
            t.created_at.strftime('%Y-%m-%d %H:%M'),
            t.sla_deadline.strftime('%Y-%m-%d %H:%M') if t.sla_deadline else '',
            'Evet' if t.is_sla_breached else 'Hayır',
            'Evet' if t.is_escalated else 'Hayır',
        ])
    return response


@login_required
def user_profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            user = request.user
            user.first_name = form.cleaned_data.get('first_name', user.first_name)
            user.last_name = form.cleaned_data.get('last_name', user.last_name)
            user.email = form.cleaned_data.get('email', user.email)
            user.save()
            messages.success(request, _('Profiliniz güncellendi.'))
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=profile, initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })
    return render(request, 'profile.html', {'form': form, 'profile': profile})


@login_required
@require_GET
def notifications_api(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'link': n.link,
                'type': n.notification_type,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
            }
            for n in notifications
        ],
    }
    return JsonResponse(data)


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@login_required
def user_management_view(request):
    if not (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Yönetim']).exists()):
        return redirect('dashboard')

    ensure_default_groups()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_user':
            form = RegisterUserForm(request.POST)
            if form.is_valid():
                user = form.save()
                role = request.POST.get('role', ROLE_CUSTOMER)
                group = Group.objects.filter(name=role).first()
                if group:
                    user.groups.add(group)
                UserProfile.objects.get_or_create(user=user)
                messages.success(request, f'Kullanıcı oluşturuldu: {user.username}')
                return redirect('user_management')
        elif action == 'edit_user':
            user = get_object_or_404(User, pk=request.POST.get('user_id'))
            edit_form = UserEditForm(request.POST, instance=user)
            if edit_form.is_valid():
                edit_form.save()
                user.groups.clear()
                role = request.POST.get('role')
                if role:
                    group = Group.objects.filter(name=role).first()
                    if group:
                        user.groups.add(group)
                messages.success(request, f'Kullanıcı güncellendi: {user.username}')
                return redirect('user_management')

    users = User.objects.prefetch_related('groups', 'profile').order_by('-date_joined')
    return render(request, 'user_management.html', {
        'users': users,
        'user_form': RegisterUserForm(),
        'roles': [ROLE_ADMIN, ROLE_SUPPORT, ROLE_CUSTOMER],
    })
