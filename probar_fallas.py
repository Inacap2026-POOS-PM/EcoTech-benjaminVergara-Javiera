import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

import cliente_api


def respuesta(codigo, datos=None, headers=None):
    """Crea una respuesta falsa de la API."""
    r = MagicMock()
    r.status_code = codigo
    r.headers = headers or {}
    r.json.return_value = datos
    return r


class PruebasDeFallas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(patch.stopall)
        # Datos falsos: no se usa la clave real ni la base real
        patch.object(cliente_api, "SUPABASE_URL", "https://prueba.supabase.co").start()
        patch.object(cliente_api, "SUPABASE_KEY", "clave-falsa-de-prueba").start()
        patch.object(cliente_api, "RUTA_BD", os.path.join(self.tmp.name, "prueba.db")).start()
        # Sin esperas reales para que las pruebas sean rápidas
        self.sleep = patch("cliente_api.time.sleep").start()

    @patch("cliente_api.requests.get")
    def test_timeout_reintenta_y_se_rinde(self, get):
        get.side_effect = requests.exceptions.Timeout()
        self.assertIsNone(cliente_api.consultar_tabla("empleados"))
        self.assertEqual(get.call_count, cliente_api.MAX_INTENTOS)

    @patch("cliente_api.requests.get")
    def test_sin_red_reintenta_y_se_rinde(self, get):
        get.side_effect = requests.exceptions.ConnectionError()
        self.assertIsNone(cliente_api.consultar_tabla("empleados"))
        self.assertEqual(get.call_count, cliente_api.MAX_INTENTOS)

    @patch("cliente_api.requests.get")
    def test_errores_4xx_no_se_reintentan(self, get):
        for codigo in (401, 403, 404):
            with self.subTest(codigo=codigo):
                get.reset_mock()
                get.return_value = respuesta(codigo)
                self.assertIsNone(cliente_api.consultar_tabla("empleados"))
                self.assertEqual(get.call_count, 1)

    @patch("cliente_api.requests.get")
    def test_429_respeta_retry_after(self, get):
        get.side_effect = [
            respuesta(429, headers={"Retry-After": "2"}),
            respuesta(200, [{"id": 1}]),
        ]
        self.assertEqual(cliente_api.consultar_tabla("empleados"), [{"id": 1}])
        self.sleep.assert_called_once_with(2.0)

    @patch("cliente_api.requests.get")
    def test_500_reintenta_y_se_recupera(self, get):
        get.side_effect = [respuesta(500), respuesta(503), respuesta(200, [{"id": 2}])]
        self.assertEqual(cliente_api.consultar_tabla("empleados"), [{"id": 2}])
        self.assertEqual(get.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)

    @patch("cliente_api.requests.get")
    def test_url_rota_no_se_cae_ni_reintenta(self, get):
        get.side_effect = requests.exceptions.InvalidURL("URL rota")
        self.assertIsNone(cliente_api.consultar_tabla("empleados"))
        self.assertEqual(get.call_count, 1)

    @patch("cliente_api.requests.get")
    def test_nombre_de_tabla_invalido_no_hace_peticion(self, get):
        self.assertIsNone(cliente_api.consultar_tabla("empleados?x=../"))
        get.assert_not_called()

    def test_plan_b_usa_datos_locales_con_aviso(self):
        cliente_api.guardar_cache("empleados", [{"rut": "1-9"}])
        with patch("cliente_api.consultar_tabla", return_value=None):
            r = cliente_api.obtener_datos("empleados")
        self.assertEqual(r["origen"], "local")
        self.assertEqual(r["datos"], [{"rut": "1-9"}])
        self.assertIn("guardados hace", r["aviso"])

    def test_plan_c_sin_api_y_sin_datos_locales(self):
        with patch("cliente_api.consultar_tabla", return_value=None):
            r = cliente_api.obtener_datos("empleados")
        self.assertEqual(r["origen"], "ninguno")
        self.assertIsNone(r["datos"])
        self.assertIn("no está disponible", r["aviso"])

    def test_api_ok_guarda_copia_local(self):
        with patch("cliente_api.consultar_tabla", return_value=[{"id": 3}]):
            r = cliente_api.obtener_datos("empleados")
        self.assertEqual(r["origen"], "api")
        datos, _momento = cliente_api.leer_cache("empleados")
        self.assertEqual(datos, [{"id": 3}])


if __name__ == "__main__":
    unittest.main()