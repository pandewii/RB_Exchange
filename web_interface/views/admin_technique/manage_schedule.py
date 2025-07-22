# web_interface/views/admin_technique/manage_schedule.py

import json
from django.shortcuts import get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source
from django_celery_beat.models import PeriodicTask, CrontabSchedule

class ManageScheduleView(View):

    def post(self, request, *args, **kwargs):
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=kwargs.get('source_id'))
        
        # Récupération des données du formulaire pour l'heure et la minute
        hour = request.POST.get('hour', '7') # 7h par défaut
        minute = request.POST.get('minute', '0') # 00 min par défaut
        enabled = request.POST.get('enabled') == 'on'

        # 1. On trouve ou on crée l'objet CrontabSchedule correspondant
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        # 2. On prépare les arguments pour la tâche Celery
        task_kwargs = json.dumps({'source_id': source.pk})

        # 3. On crée ou on met à jour la PeriodicTask
        if source.periodic_task:
            task = source.periodic_task
            task.crontab = schedule
            task.interval = None
            task.enabled = enabled
            task.kwargs = task_kwargs
            task.save()
        else:
            task_name = f"Scraper pour Source ID {source.pk} - {source.nom}"
            task = PeriodicTask.objects.create(
                crontab=schedule,
                name=task_name,
                task='scrapers.tasks.run_scraper_for_source',
                kwargs=task_kwargs,
                enabled=enabled
            )
            source.periodic_task = task
            source.save()

        # MODIFICATION : Passer 'current_user_role' au contexte pour le rendu du partiel
        context = {
            "source": source,
            "current_user_role": request.session.get('role'), # Passer le rôle explicitement
        }
        html = render_to_string("admin_technique/partials/_schedule_details.html", context, request=request)
        
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showSuccess": "Planification enregistrée avec succès."}'
        return response