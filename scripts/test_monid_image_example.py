"""Offline checks for the standalone Monid example (standard library only)."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from monid_image_example import MonidProviderError, generate_image


def response(status, body):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status = status
    result.read.return_value = json.dumps(body).encode("utf-8")
    return result


class MonidImageTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"MONID_API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.http = patch("monid_image_example.urllib.request.urlopen")
        self.urlopen = self.http.start()
        self.addCleanup(self.http.stop)

    def test_sync_request_and_utf8(self):
        self.urlopen.return_value = response(200, {"output": {"images": ["example"]}})
        self.assertEqual(generate_image("森林"), {"images": ["example"]})
        req = self.urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.monid.ai/v1/run")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(req.get_header("Content-type"), "application/json; charset=utf-8")
        self.assertIn("森林".encode("utf-8"), req.data)
        self.assertEqual(json.loads(req.data), {
            "provider": "alibaba", "endpoint": "/v1/image/wan2.7-image",
            "input": {"queryParams": {}, "body": {"prompt": "森林"}, "pathParams": {}},
        })

    @patch("monid_image_example.time.sleep")
    def test_async_polling(self, sleep):
        self.urlopen.side_effect = [
            response(202, {"runId": "run-1"}),
            response(200, {"status": "RUNNING"}),
            response(200, {"status": "COMPLETED", "output": {"images": []}}),
        ]
        self.assertEqual(generate_image("forest"), {"images": []})
        for call in self.urlopen.call_args_list[1:]:
            self.assertEqual(call.args[0].full_url, "https://api.monid.ai/v1/runs/run-1")
            self.assertEqual(call.args[0].get_method(), "GET")
            self.assertEqual(call.args[0].get_header("Authorization"), "Bearer test-key")

    def test_provider_error_without_output(self):
        for status in (400, 404, 429):
            with self.subTest(status=status):
                self.urlopen.return_value = response(200, {
                    "status": "COMPLETED",
                    "providerResponse": {"httpStatus": status, "error": {"message": "bad input"}},
                })
                with self.assertRaises(MonidProviderError) as caught:
                    generate_image("forest")
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.error, {"message": "bad input"})

    @patch("monid_image_example.time.sleep")
    def test_terminal_errors(self, sleep):
        for status in ("FAILED", "TIMED_OUT", "STOPPED", "BLOCKED"):
            with self.subTest(status=status):
                self.urlopen.side_effect = [
                    response(202, {"runId": "run-1"}), response(200, {"status": status}),
                ]
                with self.assertRaisesRegex(RuntimeError, status):
                    generate_image("forest")

    def test_http_error(self):
        self.urlopen.side_effect = urllib.error.HTTPError(
            "https://api.monid.ai/v1/run", 401, "Unauthorized", {}, io.BytesIO(b'{}'),
        )
        with self.assertRaises(urllib.error.HTTPError):
            generate_image("forest")

    @patch("monid_image_example.time.monotonic", side_effect=[0, 0, 301])
    def test_poll_deadline(self, monotonic):
        self.urlopen.return_value = response(202, {"runId": "run-1"})
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            generate_image("forest")
        self.assertEqual(self.urlopen.call_count, 1)

    def test_missing_key_does_not_request(self):
        os.environ.pop("MONID_API_KEY", None)
        with self.assertRaisesRegex(RuntimeError, "Set MONID_API_KEY"):
            generate_image("forest")
        self.urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
