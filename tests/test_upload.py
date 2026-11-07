"""图片上传：鉴权、魔数校验、大小限制、静态访问。"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _upload(client, token, content, filename="a.png", content_type="image/png"):
    headers = {"Authorization": token} if token else {}
    return client.post(
        "/api/upload/image",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def _local_path(url: str) -> Path:
    """ "http://testserver/uploads/2026/10/xx.png" -> 本地绝对路径"""
    rel = url.split("://", 1)[1].split("/", 1)[1]  # uploads/2026/10/xx.png
    return ROOT / rel


def test_upload_requires_login(client):
    assert _upload(client, "", PNG).status_code == 401


def test_upload_png_and_serve_it_back(client, temp_user):
    resp = _upload(client, temp_user["token"], PNG)
    assert resp.status_code == 201, resp.text

    url = resp.json()["data"]["url"]
    assert "/uploads/" in url and url.endswith(".png")
    assert resp.headers["Location"] == url

    try:
        path = _local_path(url)
        assert path.exists()

        got = client.get("/uploads/" + url.split("/uploads/", 1)[1])
        assert got.status_code == 200
        assert got.content == PNG
    finally:
        _local_path(url).unlink(missing_ok=True)


def test_extension_comes_from_magic_bytes_not_filename(client, temp_user):
    """文件名写成 .php 也没用：扩展名由文件头决定。"""
    resp = _upload(client, temp_user["token"], PNG, filename="shell.php", content_type="application/x-php")
    assert resp.status_code == 201, resp.text

    url = resp.json()["data"]["url"]
    try:
        assert url.endswith(".png")
        assert ".php" not in url
    finally:
        _local_path(url).unlink(missing_ok=True)


@pytest.mark.parametrize(
    "content, filename, content_type",
    [
        (b"<html>not an image</html>", "a.txt", "text/plain"),
        (b"<?php echo 1; ?>", "a.php", "application/x-php"),
        (b"", "empty.png", "image/png"),
    ],
)
def test_upload_rejects_non_image(client, temp_user, content, filename, content_type):
    resp = _upload(client, temp_user["token"], content, filename=filename, content_type=content_type)
    assert resp.status_code in (415, 422)


def test_upload_rejects_oversized_file(client, temp_user):
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024)
    resp = _upload(client, temp_user["token"], big)
    assert resp.status_code == 413
    assert "5MB" in resp.json()["message"]
