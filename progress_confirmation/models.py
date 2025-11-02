from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class Process(models.Model):
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(help_text="工程の順序（小さいほど前工程）")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ("未着手", "未着手"),
        ("進行中", "進行中"),
        ("完了", "完了"),
    ]

    order_no = models.CharField(max_length=30, unique=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    due_date = models.DateField()
    current_process = models.ForeignKey(
        Process,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_orders",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="未着手")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order_no} — {self.product_name}"

    @property
    def progress(self):
        """
        進捗率（工程の順序から簡易計算）
        """
        processes = list(Process.objects.all().order_by("order"))
        if not processes:
            return 0
        if not self.current_process:
            return 0
        try:
            idx = processes.index(self.current_process)
        except ValueError:
            return 0
        return int(((idx) / (len(processes) - 1 if len(processes) > 1 else 1)) * 100)


class ProgressLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    process = models.ForeignKey(Process, on_delete=models.CASCADE)
    worker_name = models.ForeignKey(
        "Worker", on_delete=models.SET_NULL, null=True, blank=True
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.order} - {self.process} by {self.worker_name or '---'}"


class WorkerManager(BaseUserManager):
    def create_user(self, employee_id, name, password=None, **extra_fields):
        if not employee_id:
            raise ValueError("社員IDは必須です")
        user = self.model(employee_id=employee_id, name=name, **extra_fields)
        user.set_password(password)  # ← ハッシュ化される
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_id, name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(employee_id, name, password, **extra_fields)


class Worker(AbstractBaseUser, PermissionsMixin):
    employee_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    hire_date = models.DateField(blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # 管理サイトにアクセスできるかどうか

    objects = WorkerManager()

    USERNAME_FIELD = "employee_id"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        return self.name
