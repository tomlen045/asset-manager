from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """系统用户：工号登录，扩展员工信息"""
    employee_id = models.CharField('工号', max_length=20, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)

    class Meta:
        db_table = 'accounts_user'
