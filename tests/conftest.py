import os

import pytest
from django.contrib.auth.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(username="alice", password="senha-segura-123", email="alice@example.com")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="bob", password="senha-segura-123")
