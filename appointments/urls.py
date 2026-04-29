"""appointments URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from appointment.views_api import (
    capacity_status_api, enter_api, leave_api, staff_capacity_page, today_queue_api, user_capacity_page
)

urlpatterns = [
    path("", RedirectView.as_view(url="/capacity/", permanent=False), name="home"),
    path("zh-CN/admin/", RedirectView.as_view(url="/zh-hans/admin/", permanent=False)),
    path("zh-CN/", RedirectView.as_view(url="/zh-hans/", permanent=False)),
    path("capacity/", user_capacity_page, name="capacity_page"),
    path("capacity/staff/", staff_capacity_page, name="staff_capacity_page"),
    path("api/status/", capacity_status_api, name="capacity_status_api"),
    path("api/queue/today/", today_queue_api, name="today_queue_api"),
    path("api/enter/", enter_api, name="enter_api"),
    path("api/leave/", leave_api, name="leave_api"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path("", include("appointment.urls")),
)
