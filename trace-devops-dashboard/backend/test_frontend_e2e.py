"""
Teste ponta a ponta do painel novo (fetch -> API) contra um servidor
uvicorn real (repositorio fake, ver _dev_fake_server.py -- sem Oracle
real, mesma limitacao dos outros testes desta sessao). Sobe o FastAPI de
verdade como subprocesso, serve o frontend estatico de verdade, e dirige
um navegador de verdade (Playwright) fazendo fetch() de verdade contra
ele.

Precisa de: playwright (node, ja instalado em /opt/node22) e o Chromium
de /opt/pw-browsers. Roda: python test_frontend_e2e.py
"""
import subprocess
import sys
import time
import urllib.request

PORT = 8129
NODE = "/opt/node22/bin/node"
NODE_ENV = {"NODE_PATH": "/opt/node22/lib/node_modules", "PATH": "/usr/bin:/bin:/opt/node22/bin"}

NODE_SCRIPT = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch({{ executablePath: '/opt/pw-browsers/chromium' }});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('response', r => {{ if (r.status() >= 400 && !r.url().includes('favicon')) errors.push('HTTP ' + r.status() + ': ' + r.url()); }});

  await page.goto('http://127.0.0.1:{PORT}/', {{ waitUntil: 'networkidle' }});
  await page.waitForTimeout(400);

  await page.selectOption('#analista-select', 'Larissa');
  await page.waitForTimeout(600);

  const out = {{}};
  out.rows = await page.$$eval('.list-item', els => els.length);
  out.summary = await page.$$eval('.summary-value', els => els.map(e => e.textContent.trim()));
  out.detailVisible = await page.$('.detail-title') !== null;

  await page.selectOption('#detail-status', 'Publicado');
  await page.waitForTimeout(400);
  out.toastAfterStatus = await page.textContent('#toast');

  const recId = await page.getAttribute('[data-add-obs]', 'data-add-obs');
  await page.fill('#obs-input-' + recId, 'Teste: liguei pro solicitante.');
  await page.check('#obs-compromisso-' + recId);
  await page.click('[data-add-obs="' + recId + '"]');
  await page.waitForTimeout(500);
  out.toastAfterObs = await page.textContent('#toast');
  out.compromissosAfterAdd = await page.$$eval('.compromisso-row', els => els.length);

  const resolveBtn = await page.$('button.resolve');
  if (resolveBtn) {{
    await resolveBtn.click();
    await page.waitForTimeout(500);
    out.toastAfterResolve = await page.textContent('#toast');
  }}
  out.compromissosAfterResolve = await page.$$eval('.compromisso-row', els => els.length);

  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
}})();
"""

with open("/tmp/_e2e_test.js", "w") as f:
    f.write(NODE_SCRIPT)

server = subprocess.Popen(
    [sys.executable, "_dev_fake_server.py"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        print("Servidor não respondeu a tempo.")
        sys.exit(1)

    result = subprocess.run(
        [NODE, "/tmp/_e2e_test.js"],
        capture_output=True, text=True, timeout=60, env=NODE_ENV,
    )
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

if result.stderr.strip():
    print("STDERR:", result.stderr.strip())

import json  # noqa: E402

try:
    out = json.loads(result.stdout.strip().splitlines()[-1])
except Exception as e:
    print("Não consegui parsear a saída do Playwright:", e)
    print("STDOUT:", result.stdout)
    sys.exit(1)

fails = []


def check(name, cond):
    print(("OK  " if cond else "FAIL") + " " + name)
    if not cond:
        fails.append(name)


check("2 itens da Larissa na lista", out["rows"] == 2)
check("resumo: total=2", out["summary"][0] == "2")
check("painel de detalhe visível", out["detailVisible"])
check("toast após mudar status", "Atualizado" in out["toastAfterStatus"])
check("toast após observação com compromisso", "Compromisso registrado" in out["toastAfterObs"])
check("compromisso aparece na lista após adicionar", out["compromissosAfterAdd"] == 1)
check("toast após resolver", "concluído" in out.get("toastAfterResolve", ""))
check("compromisso some da lista após resolver", out["compromissosAfterResolve"] == 0)
check("zero erros HTTP/JS (fora favicon)", out["errors"] == [])

print()
if fails:
    print(f"{len(fails)} FALHA(S):", fails)
    sys.exit(1)
print("Todos os checks E2E passaram (servidor real + navegador real + fetch real).")
