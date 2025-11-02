from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("order/<int:pk>/", views.order_detail, name="order_detail"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path(
        "order/<int:order_id>/start/<int:process_id>/",
        views.start_process,
        name="start_process",
    ),
    path(
        "order/<int:order_id>/complete/<int:process_id>/",
        views.complete_process,
        name="complete_process",
    ),
    path("order_add/", views.order_add, name="order_add"),
    path("workers/", views.worker_list, name="worker_list"),
    path("workers/add/", views.worker_add, name="worker_add"),
    path("workers/<int:pk>/edit/", views.worker_edit, name="worker_edit"),
    path("workers/<int:pk>/delete/", views.worker_delete, name="worker_delete"),
    path("login/", views.worker_login, name="login"),
    path("logout/", views.worker_logout, name="logout"),
]
