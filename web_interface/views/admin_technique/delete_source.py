from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from core.models import Source

class DeleteSourceView(View):

    def get(self, request, *args, **kwargs):
        # Pour une requête GET, on trouve la source et on affiche la modale de confirmation.
        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        return render(request, "admin_technique/partials/form_delete_source.html", {"source": source})

    def post(self, request, *args, **kwargs):
        # Pour une requête POST, on effectue la suppression.
        if request.session.get("role") != "ADMIN_TECH":
            return HttpResponse("Accès non autorisé.", status=403)

        source = get_object_or_404(Source, pk=kwargs.get('pk'))
        zone = source.zone # On garde une référence à la zone avant de supprimer la source
        
        # En supprimant la source, Django va automatiquement supprimer en cascade
        # toutes les ScrapedCurrencyRaw qui lui sont liées, grâce au on_delete=models.CASCADE.
        source.delete()

        # On prépare le nouveau contexte pour le fragment de page.
        # Comme la source est supprimée, on passe 'source': None.
        context = {"zone": zone, "source": None}
        html = render_to_string("admin_technique/partials/_source_details.html", context)
        
        # On renvoie le HTML mis à jour et on déclenche une notification.
        response = HttpResponse(html)
        response['HX-Trigger'] = '{"showInfo": "Source et données associées supprimées avec succès."}'
        return response