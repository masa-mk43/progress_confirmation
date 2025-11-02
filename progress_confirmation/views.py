from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Avg, Case, When, FloatField
from .models import Order, Process, ProgressLog, Worker
from .forms import OrderForm, CSVUploadForm, WorkerForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
import csv
import io


def index(request):
    # フィルタ（検索・状態）
    q = request.GET.get("q", "")
    status = request.GET.get("status", "")
    orders = Order.objects.all().order_by("due_date")

    if q:
        orders = orders.filter(Q(order_no__icontains=q) | Q(product_name__icontains=q))
    if status:
        orders = orders.filter(status=status)

    processes = Process.objects.all()
    # カードで使う progress プロパティはモデルに定義済み
    return render(
        request,
        "progress_confirmation/index.html",
        {
            "orders": orders,
            "processes": processes,
            "q": q,
            "status": status,
        },
    )


def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    processes = Process.objects.all()
    logs = ProgressLog.objects.filter(order=order).order_by("-start_time")
    return render(
        request,
        "progress_confirmation/order_detail.html",
        {
            "order": order,
            "processes": processes,
            "logs": logs,
        },
    )


def start_process(request, order_id, process_id):
    order = get_object_or_404(Order, pk=order_id)
    process = get_object_or_404(Process, pk=process_id)

    # すでに同じ工程が進行中なら警告
    existing_log = ProgressLog.objects.filter(
        order=order, process=process, end_time__isnull=True
    ).first()

    if existing_log:
        messages.warning(request, f"{process.name} はすでに進行中です。終了処理を行ってください。")
        return redirect("order_detail", pk=order_id)

    # 🔸 前工程が未完了なら開始をブロック
    processes = list(Process.objects.all().order_by("order"))
    try:
        idx = processes.index(process)
        if idx > 0:
            prev_process = processes[idx - 1]
            prev_log = ProgressLog.objects.filter(order=order, process=prev_process).order_by("-end_time").first()

            # 前工程が完了していない場合
            if not prev_log or prev_log.end_time is None:
                messages.warning(
                    request,
                    f"前工程「{prev_process.name}」がまだ完了していません。完了処理を行ってから次工程を開始してください。",
                )
                return redirect("order_detail", pk=order_id)
    except ValueError:
        pass  # process がリストにない（念のため）

    # 🔹 正常に開始可能
    ProgressLog.objects.create(
        order=order,
        process=process,
        start_time=timezone.now(),
        worker_name=request.user if request.user.is_authenticated else None,
    )

    order.current_process = process
    order.status = "進行中"
    order.save()

    messages.success(request, f"{order.order_no} の {process.name} を開始しました。")
    return redirect("order_detail", pk=order_id)


def complete_process(request, order_id, process_id):
    order = get_object_or_404(Order, pk=order_id)
    process = get_object_or_404(Process, pk=process_id)

    # 🔸 未完了ログ（進行中ログ）を取得
    log = (
        ProgressLog.objects.filter(
            order=order, process=process, end_time__isnull=True
        )
        .order_by("-start_time")
        .first()
    )

    # 🔹 進行中ログが存在しない → 警告
    if not log:
        messages.warning(
            request,
            f"{process.name} はまだ開始されていません。開始処理を行ってから完了してください。",
        )
        return redirect("order_detail", pk=order_id)

    # 🔹 正常に完了処理
    log.end_time = timezone.now()
    log.save()

    # 次工程または完了ステータスに更新
    processes = list(Process.objects.all().order_by("order"))

    try:
        idx = processes.index(order.current_process)
        if idx + 1 < len(processes):
            order.current_process = processes[idx + 1]
            order.status = "進行中"
        else:
            order.status = "完了"
    except Exception:
        order.status = "完了"

    order.save()
    messages.success(request, f"{order.order_no} の {process.name} を完了しました。")
    return redirect("order_detail", pk=order_id)


def dashboard(request):
    total_orders = Order.objects.count()
    completed = Order.objects.filter(status="完了").count()
    in_progress = Order.objects.filter(status="進行中").count()
    waiting = total_orders - completed - in_progress
    orders = Order.objects.all().annotate(
        annotated_progress=Case(
            When(status="完了", then=100.0),
            When(status="進行中", then=50.0),
            When(status="未着手", then=0.0),
            default=0.0,
            output_field=FloatField(),
        )
    )
    avg_progress = (
        orders.aggregate(Avg("annotated_progress"))["annotated_progress__avg"] or 0
    )

    context = {
        "total_orders": total_orders,
        "orders": orders,
        "completed": completed,
        "in_progress": in_progress,
        "waiting": waiting,
        "avg_progress": round(avg_progress, 1),
    }
    return render(request, "progress_confirmation/dashboard.html", context)


def order_add(request):
    """単品登録 or CSV一括登録ページ"""
    if request.method == "POST":
        # 単品登録フォーム
        if "single_submit" in request.POST:
            form = OrderForm(request.POST)
            if form.is_valid():
                order = form.save(commit=False)
                # 最初の工程を設定（あれば）
                first_process = Process.objects.order_by("order").first()
                order.current_process = first_process
                order.status = "未着手"
                order.save()
                messages.success(request, f"{order.order_no} を登録しました。")
                return redirect("index")
        # CSV一括登録
        elif "csv_submit" in request.POST:
            csv_form = CSVUploadForm(request.POST, request.FILES)
            if csv_form.is_valid():
                csv_file = csv_form.cleaned_data["csv_file"]
                decoded_file = csv_file.read().decode("utf-8")
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                count = 0
                for row in reader:
                    order = Order(
                        order_no=row.get("order_no"),
                        # customer=row.get("customer"),
                        product_name=row.get("product_name"),
                        quantity=row.get("quantity") or 0,
                        due_date=row.get("due_date"),
                        status="未着手",
                    )
                    first_process = Process.objects.order_by("order").first()
                    order.current_process = first_process
                    order.save()
                    count += 1
                messages.success(request, f"{count} 件の受注を登録しました。")
                return redirect("index")
    else:
        form = OrderForm()
        csv_form = CSVUploadForm()

    return render(
        request, "progress_confirmation/order_add.html", {"form": form, "csv_form": csv_form}
    )


# 作業者管理
# 一覧
def worker_list(request):
    workers = Worker.objects.all().order_by("employee_id")
    return render(request, "progress_confirmation/worker_list.html", {"workers": workers})


# 登録
def worker_add(request):
    if request.method == "POST":
        employee_id = request.POST.get("employee_id")
        name = request.POST.get("name")
        password = request.POST.get("password")
        hire_date = request.POST.get("hire_date")
        department = request.POST.get("department")
        is_active = "is_active" in request.POST

        if Worker.objects.filter(employee_id=employee_id).exists():
            messages.error(request, "この社員IDは既に登録されています。")
        else:
            Worker.objects.create(
                employee_id=employee_id,
                name=name,
                password=make_password(password),
                hire_date=hire_date or None,
                department=department or "",
                is_active=is_active,
            )
            messages.success(request, f"{name} さんを登録しました。")
            return redirect("worker_list")

    return render(request, "progress_confirmation/worker_add.html")


# 編集
def worker_edit(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        form = WorkerForm(request.POST, instance=worker)
        if form.is_valid():
            form.save()
            messages.success(request, f"{worker.name} さんの情報を更新しました。")
            return redirect("worker_list")
        else:
            messages.error(request, "入力内容にエラーがあります。")
    else:
        form = WorkerForm(instance=worker)
    return render(request, "progress_confirmation/worker_edit.html", {"form": form, "worker": worker})


# 削除
def worker_delete(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        worker.delete()
        messages.success(request, "作業者を削除しました。")
        return redirect("worker_list")
    return render(request, "progress_confirmation/worker_confirm_delete.html", {"worker": worker})


def worker_login(request):
    if request.method == "POST":
        employee_id = request.POST["employee_id"]
        password = request.POST["password"]
        user = authenticate(request, employee_id=employee_id, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")  # ダッシュボードへ
        else:
            return render(
                request,
                "progress_confirmation/login.html",
                {"error": "社員IDまたはパスワードが違います"},
            )
    return render(request, "progress_confirmation/login.html")


def worker_logout(request):
    logout(request)
    return redirect("login")
