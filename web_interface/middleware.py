from django.utils.cache import add_never_cache_headers

class NoCacheMiddleware:
    """
    Ce middleware ajoute des en-têtes à chaque réponse pour dire
    au navigateur de ne jamais mettre cette page en cache.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # On récupère la réponse que Django s'apprêtait à envoyer
        response = self.get_response(request)
        
        # On y ajoute les en-têtes "never_cache"
        add_never_cache_headers(response)
        
        return response
