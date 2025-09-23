"""
Custom middleware for handling CSRF exemptions
"""
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
import re


class CSRFExemptMiddleware(MiddlewareMixin):
    """
    Middleware to exempt certain URL patterns from CSRF validation
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        # Define URL patterns that should be exempt from CSRF
        self.exempt_patterns = [
            re.compile(r'^/api/'),  # All API endpoints
        ]
    
    def process_request(self, request):
        """
        Check if the request path matches any exempt patterns
        and disable CSRF for those requests
        """
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            for pattern in self.exempt_patterns:
                if pattern.match(request.path_info):
                    # Disable CSRF check for this request
                    setattr(request, '_dont_enforce_csrf_checks', True)
                    break
        
        return None
