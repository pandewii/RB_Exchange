# web_interface/views/admin_zone/dashboard.py

from django.shortcuts import render, redirect, get_object_or_404
from core.models import Devise, ActivatedCurrency, ZoneMonetaire, Source, ScrapedCurrencyRaw, DeviseAlias
from logs.models import LogEntry
from django.db.models import Q
from django.views import View

class AdminZoneDashboardView(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "ADMIN_ZONE":
            return redirect('login')

        user_managed_zone = request.user.zone

        # Debug prints (can be removed after verifying fix)
        print(f"DEBUG: User email: {request.user.email}")
        print(f"DEBUG: User role: {request.user.role}")
        print(f"DEBUG: User zone object: {request.user.zone}")
        if request.user.zone:
            print(f"DEBUG: User zone name: {request.user.zone.nom}")
            print(f"DEBUG: User zone ID: {request.user.zone.pk}")
        else:
            print("DEBUG: User zone is None or evaluates to False")
            # This block handles truly unassigned Admin Zone users
            context = {
                'error': "Votre compte n'est pas associé à une zone monétaire. Veuillez contacter l'administrateur technique.", # Use 'error' consistently
                'current_user_role': request.user.role,
                'critical_errors_logs': [],
                'all_mapped_devises': Devise.objects.none(), # Use correct variable name and empty queryset
                'active_codes': set(),
                'zone': None, # Explicitly set zone to None here
            }
            return render(request, "admin_zone/dashboard.html", context)


        # --- Main logic to get mapped currencies ---
        # Assuming Source is OneToOne with ZoneMonetaire
        source_for_zone = Source.objects.filter(zone=user_managed_zone).first()
        all_mapped_devises = Devise.objects.none() # Initialize an empty queryset

        if source_for_zone:
            scraped_raw_currencies_in_zone = ScrapedCurrencyRaw.objects.filter(source=source_for_zone)

            raw_names_and_codes = set()
            for raw_currency in scraped_raw_currencies_in_zone:
                if raw_currency.nom_devise_brut:
                    raw_names_and_codes.add(raw_currency.nom_devise_brut.upper())
                if raw_currency.code_iso_brut:
                    raw_names_and_codes.add(raw_currency.code_iso_brut.upper())

            if raw_names_and_codes:
                all_mapped_devises = Devise.objects.filter(
                    aliases__alias__in=list(raw_names_and_codes)
                ).distinct().order_by('code')

        # Get currently active currencies for this zone
        active_currency_objects = ActivatedCurrency.objects.filter(
            zone=user_managed_zone,
            is_active=True
        ).values_list('devise__code', flat=True)
        active_codes = set(active_currency_objects)

        # Retrieve critical/error logs
        critical_errors_logs = LogEntry.objects.filter(
            Q(level__in=['error', 'critical']) |
            (Q(level='warning') & ~Q(action__in=['PIPELINE_UNMAPPED_CURRENCY', 'PIPELINE_INACTIVE_CURRENCY']))
        ).filter(
            Q(zone=user_managed_zone) |
            Q(actor=request.user) |
            Q(impersonator=request.user)
        ).order_by('-timestamp')[:5]

        context = {
            'all_mapped_devises': all_mapped_devises, # Ensure this is the correct variable name
            'active_codes': active_codes,
            'current_user_role': request.user.role,
            'critical_errors_logs': critical_errors_logs,
            'error': None, # Set to None unless an error truly occurred
            'zone': user_managed_zone, # Pass the zone object
        }

        return render(request, "admin_zone/dashboard.html", context)