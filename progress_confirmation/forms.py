from django import forms
from .models import Order, Worker


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["order_no", "product_name", "quantity", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(label="CSVファイルを選択")


class WorkerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="パスワード", required=False)

    class Meta:
        model = Worker
        fields = [
            "employee_id",
            "name",
            "hire_date",
            "department",
            "password",
            "is_active",
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 既存レコード（編集時）はパスワードを任意にする
        if self.instance and self.instance.pk:
            self.fields["password"].required = False
        else:
            # 新規登録時は必須に
            self.fields["password"].required = True

    def save(self, commit=True):
        worker = super().save(commit=False)
        password = self.cleaned_data.get("password")

        # 新規 or パスワード変更時のみセット
        if password:
            worker.set_password(password)
        elif not self.instance.pk:
            # 念のため、新規時に空パスワードが通らないようにブロック
            raise forms.ValidationError("パスワードは必須です。")

        if commit:
            worker.save()
        return worker
