from django.contrib import admin
from .models import Process, Order, ProgressLog, Worker


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("name", "order")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_no",
        "product_name",
        "quantity",
        "due_date",
        "status",
        "current_process",
    )
    list_filter = ("status", "due_date")
    search_fields = ("order_no", "product_name")


@admin.register(ProgressLog)
class ProgressLogAdmin(admin.ModelAdmin):
    list_display = ("order", "process", "worker_name", "start_time", "end_time")
    list_filter = ("process",)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "name", "department", "hire_date", "is_active")
