# web_interface/views/common/audit_logs.py

from django.shortcuts import render, redirect, get_object_or_404 
from django.views import View
from django.db.models import Q
from logs.models import LogEntry, UINotification
from users.models import CustomUser
from django.http import HttpResponse
# CORRECTION: Importation correcte des exceptions de pagination
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class AuditLogView(View):
    """
    Vue pour afficher l'historique détaillé des logs du système.
    Elle permet de filtrer par recherche textuelle et de paginer.
    """
    def get(self, request, *args, **kwargs):
        user_role = request.session.get('role')
        user_id = request.session.get('user_id')

        if not user_id or user_role not in ['SUPERADMIN', 'ADMIN_TECH', 'ADMIN_ZONE']:
            return redirect('login') 

        # Initialisation de la requête de base
        logs_queryset = LogEntry.objects.select_related('actor', 'impersonator', 'target_user').order_by('-timestamp')

        # Application du filtre de recherche (uniquement la barre de recherche)
        search_query = request.GET.get('q', '').strip()
        if search_query:
            logs_queryset = logs_queryset.filter(
                Q(action__icontains=search_query) |
                Q(details__icontains=search_query) |
                Q(actor__email__icontains=search_query) |
                Q(impersonator__email__icontains=search_query) |
                Q(target_user__email__icontains=search_query)
            )

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(logs_queryset, 20) 
        try:
            logs = paginator.page(page)
        # CORRECTION: Capturer les exceptions spécifiques de Paginator
        except (PageNotAnInteger, EmptyPage):
            # Si le numéro de page n'est pas un entier ou est hors limites, affiche la dernière page
            logs = paginator.page(paginator.num_pages)

        context = {
            'logs': logs,
            'current_user_role': user_role, 
            'search_query': search_query, 
        }

        # Si c'est une requête HTMX, rendre seulement le partial
        if request.headers.get('HX-Request'):
            # Chemin direct vers le partial
            return render(request, "common/_audit_log_table.html", context) 
            
        return render(request, "common/audit_log.html", context)


# La classe MarkUINotificationReadView doit rester ici si elle est liée à cet url (mark_notification_read)
# Ou être déplacée vers un fichier de vues plus approprié si ses URLs sont ailleurs
class MarkUINotificationReadView(View):
    def post(self, request, pk):
        if not request.session.get('user_id'):
            return HttpResponse("Non authentifié.", status=401)
        
        notification = get_object_or_404(UINotification, pk=pk, user__pk=request.session.get('user_id'))
        notification.is_read = True
        notification.save()
        
        return HttpResponse(status=204)