from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from accounts.forms import EmailAuthenticationForm
from core.views import landing_page

login_view = auth_views.LoginView.as_view(
    template_name='registration/login.html',
    authentication_form=EmailAuthenticationForm,
    redirect_authenticated_user=True,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('dashboard/', landing_page, name='dashboard'),
    path('users/', include('accounts.urls')),
    path('assets/', include('assets.urls')),
    path('tickets/', include('tickets.urls')),
    path('reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
