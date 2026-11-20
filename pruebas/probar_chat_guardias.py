# -*- coding: utf-8 -*-
"""probar_chat_guardias — los GUARDIAS del chat de amigos (servidor/social.py), 20-nov-2026.

Benja: «quita el aviso "se borrará en 2 días"; pon pruebas o guards para que no manden miles de mensajes cortos o
largos, también prueba tipos de ataque: que el chat de amigos no se pueda usar para llenar el disco duro o hacer
muchísimo spam; un guard de 1 GB: si pasa ese límite, se van borrando los mensajes más viejos de todos».

Se llama a `social` directo, con el reloj que se quiera (`ahora`): un minuto o un día se prueban sin esperarlos.
Cada ataque con su control al revés (⟲: lo normal sigue pasando, o el freno se suelta a su tiempo).
  1 · la FORMA: zalgo · cientos de líneas · emojis «gordos» · invisibles y de control · vacío · demasiado largo
  2 · la RÁFAGA: 10 cada 10 s, 40 por minuto
  3 · el mismo texto una y otra vez
  4 · cientos sin leer a una misma persona
  5 · el día: 2.000 mensajes o 300 KB
  6 · muchas cuentas a la vez (60 por segundo entre todos)
  7 · el TOPE del disco: al pasarlo se borran los más viejos de todos ⟲ debajo del tope no se borra nada
  8 · pedidos de amistad: 30 por hora
"""
import contextlib
import hashlib
import io
import os
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
fallos = []


def ok(cond, que):
    print(("  ✔ " if cond else "  ✘ ") + que)
    if not cond:
        fallos.append(que)


tmp = tempfile.mkdtemp(prefix="chat_guardias_")
os.environ.update({
    "R2_CUENTAS_DUENA": "1", "R2_CUENTAS_BASE": os.path.join(tmp, "cuentas.db"),
    "R2_PORTERO_BASE": os.path.join(tmp, "portero.db"), "R2_PORTERO_CLAVE": os.path.join(tmp, "clave.json"),
    "R2_BASE": os.path.join(tmp, "no_existe.db"), "R2_ADMIN_ARCHIVO": os.path.join(tmp, "admin.txt"),
    "R2_MODERADOR_ARCHIVO": os.path.join(tmp, "mod.txt"), "R2_PORTERO_PUERTO": "0",
})
for k in ("R2_PRESENCIA", "R2_CHAT_TOPE_MB", "R2_UID_NUEVAS_DESDE"):
    os.environ.pop(k, None)
from servidor import portero as P          # noqa: E402
from servidor import social as S           # noqa: E402

T0 = time.time()


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest().upper()


_N = [0]


def cuenta(u):
    _N[0] += 1                                    # (una IP por cuenta: el portero frena muchas altas desde una misma)
    ip = f"10.9.{_N[0] // 200}.{_N[0] % 200 + 1}"
    with contextlib.redirect_stdout(io.StringIO()):
        uid = P.registrar(u, clave_txt="clave-" + u, ip=ip)[1]["uid"]
        tok = P.entrar(u, clave_txt="clave-" + u, ip=ip)[1]["sesion"]
    return uid, tok


def amigos(a, b):
    S.pedir(P, a[1], str(b[0]), ahora=T0)
    S.responder(P, b[1], a[0], True, ahora=T0)


def limpio():
    S._freno.clear(); S._repes.clear(); S._global.clear(); S._freno_pedir.clear()


ANA, BETO, CARO = cuenta("ana_g"), cuenta("beto_g"), cuenta("caro_g")
amigos(ANA, BETO)
amigos(ANA, CARO)
C = P._cuentas()


def enviar(de, para, texto, t):
    return S.enviar(P, de[1], para[0], texto, ahora=t)


def ultimo_texto():
    return C.execute("SELECT texto FROM mensajes ORDER BY id DESC LIMIT 1").fetchone()[0]


print("1 · la forma")
limpio()
cod, d = enviar(ANA, BETO, "h" + "́" * 40 + "ola", T0)
ok(cod == 200 and ultimo_texto() == "h́́ola", "zalgo: 40 tildes encima de una letra quedan en 2")
cod, d = enviar(ANA, BETO, "\n".join(f"línea {i}" for i in range(300)), T0 + 1)
ok(cod == 200 and ultimo_texto().count("\n") == 11, f"300 líneas quedan en 12 ({ultimo_texto().count(chr(10)) + 1})")
cod, d = enviar(ANA, BETO, "\U0001F600" * 500, T0 + 2)
ok(cod == 200 and len(ultimo_texto().encode("utf-8")) <= 2000, f"500 emojis de 4 bytes: ≤ 2.000 bytes ({len(ultimo_texto().encode())})")
cod, d = enviar(ANA, BETO, "a​b‮c\x00d\x07e", T0 + 3)
ok(cod == 200 and ultimo_texto() == "abcde", f"invisibles, al revés y de control: fuera ({ultimo_texto()!r})")
cod, _ = enviar(ANA, BETO, "​​ \n\n \x00", T0 + 4)
ok(cod == 400, f"⟲ sólo invisibles y espacios = vacío: 400 ({cod})")
cod, _ = enviar(ANA, BETO, "x" * 100_000, T0 + 5)
ok(cod == 200 and len(ultimo_texto()) == 500, "100.000 letras: entra sólo hasta 500")
cod, _ = enviar(ANA, BETO, "¡Hola, Beto! ¿Jugamos una carrera? 🎮\nDale.", T0 + 6)
ok(cod == 200 and ultimo_texto() == "¡Hola, Beto! ¿Jugamos una carrera? 🎮\nDale.", "⟲ un mensaje normal (con ñ, tildes, un emoji y 2 líneas) queda IGUAL")

print("2 · la ráfaga")
limpio()
res = [enviar(ANA, BETO, f"r{i}", T0 + 100 + i * 0.1)[0] for i in range(11)]
ok(res[:10] == [200] * 10 and res[10] == 429, f"10 en un segundo pasan; el 11.º, 429 ({res[-1]})")
cod, _ = enviar(ANA, BETO, "r-despues", T0 + 100 + 10.5)
ok(cod == 200, f"⟲ pasados 10 s, puede seguir ({cod})")
limpio()
res = [enviar(ANA, BETO, f"m{i}", T0 + 200 + i * 1.1)[0] for i in range(41)]
ok(res[:40] == [200] * 40 and res[40] == 429, f"de a uno por segundo: 40 en el minuto, el 41.º 429 ({res.count(200)} pasaron)")
cod, _ = enviar(ANA, BETO, "m-despues", T0 + 200 + 41 * 1.1 + 61)
ok(cod == 200, f"⟲ al minuto siguiente, puede seguir ({cod})")

print("3 · el mismo texto")
limpio()
res = [enviar(ANA, BETO, "spam spam", T0 + 400 + i * 5)[0] for i in range(3)]
ok(res == [200, 200, 429], f"el mismo texto: 2 pasan, el 3.º 429 ({res})")
cod, _ = enviar(ANA, BETO, "otra cosa", T0 + 416)
ok(cod == 200, "⟲ otro texto sí")
cod, _ = enviar(ANA, CARO, "spam spam", T0 + 417)
ok(cod == 200, "⟲ el mismo texto a OTRA persona sí")
cod, _ = enviar(ANA, BETO, "spam spam", T0 + 400 + 125)
ok(cod == 200, "⟲ pasados 2 minutos, el mismo texto vuelve a pasar")

print("4 · cientos sin leer")
limpio()
with P._escribir:
    C.execute("UPDATE mensajes SET leido = 1")
    C.executemany("INSERT INTO mensajes (de, para, texto, cuando) VALUES (?, ?, ?, ?)",
                  [(ANA[0], BETO[0], f"sl{i}", int(T0 + 600)) for i in range(S.SIN_LEER_MAX)])
    C.commit()
cod, d = enviar(ANA, BETO, "uno más", T0 + 700)
ok(cod == 429 and "sin leer" in d.get("error", ""), f"con {S.SIN_LEER_MAX} sin leer a Beto: 429 ({cod})")
cod, _ = enviar(ANA, CARO, "a Caro sí", T0 + 701)
ok(cod == 200, "⟲ a otra persona sí puede")
S.chat(P, BETO[1], ANA[0], ahora=T0 + 702)
cod, _ = enviar(ANA, BETO, "ya leyó", T0 + 703)
ok(cod == 200, "⟲ cuando Beto abre el chat (lee), puede volver a escribirle")

print("5 · el día")
limpio()
DIA = T0 + 5 * 86400
with P._escribir:
    C.execute("UPDATE mensajes SET leido = 1")
    C.executemany("INSERT INTO mensajes (de, para, texto, cuando, leido) VALUES (?, ?, ?, ?, 1)",
                  [(ANA[0], CARO[0], f"d{i}", int(DIA - 3600)) for i in range(S.DIA_MSG - 1)])
    C.commit()
cod, _ = enviar(ANA, CARO, "el 2000", DIA)
cod2, d2 = enviar(ANA, CARO, "el 2001", DIA + 1)
ok(cod == 200 and cod2 == 429 and "hoy" in d2.get("error", ""), f"el mensaje 2.000 del día pasa; el 2.001, 429 ({cod}, {cod2})")
limpio()
cod, _ = enviar(ANA, CARO, "al otro día", DIA + 86400)
ok(cod == 200, "⟲ al día siguiente (lo de ayer ya no cuenta) puede seguir")
limpio()
D2 = DIA + 3 * 86400
with P._escribir:
    C.executemany("INSERT INTO mensajes (de, para, texto, cuando, leido) VALUES (?, ?, ?, ?, 1)",
                  [(CARO[0], ANA[0], "z" * 500, int(D2 - 60)) for _ in range(S.DIA_BYTES // 500 - 1)])
    C.commit()
cod, _ = enviar(CARO, ANA, "w" * 499, D2)
cod2, _ = enviar(CARO, ANA, "w" * 500, D2 + 1)
ok(cod == 200 and cod2 == 429, f"300 KB por día: el que llena pasa, el que se pasa 429 ({cod}, {cod2})")

print("6 · muchas cuentas a la vez")
limpio()
G = D2 + 86400 * 2
S._global[:] = [G] * S.GLOBAL_SEG
cod, d = enviar(BETO, ANA, "entre todos", G)
ok(cod == 503, f"con {S.GLOBAL_SEG} mensajes en este segundo entre todos: 503 ({cod})")
cod, _ = enviar(BETO, ANA, "un segundo después", G + 1.1)
ok(cod == 200, "⟲ al segundo siguiente, pasa")

print("7 · el tope del disco")
limpio()
os.environ["R2_CHAT_TOPE_MB"] = "1024"
S._tam["bytes"] = None
antes = C.execute("SELECT COUNT(*) FROM mensajes").fetchone()[0]
cod, _ = enviar(BETO, ANA, "con 1 GB de tope", G + 10)
ok(cod == 200 and C.execute("SELECT COUNT(*) FROM mensajes").fetchone()[0] == antes + 1, "⟲ debajo del tope (1 GB) no se borra nada")
ok(S.tope_bytes() == 1024 ** 3, "de fábrica el tope es 1 GB")
os.environ["R2_CHAT_TOPE_MB"] = "0.25"                   # 256 KB para la prueba (lo de arriba ya ocupa más)
S._tam["bytes"] = None
tope = S.tope_bytes()
total = lambda: C.execute("SELECT COALESCE(SUM(length(CAST(texto AS BLOB))), 0) + COUNT(*) * ? FROM mensajes",  # noqa: E731
                          (S.FILA_BYTES,)).fetchone()[0]
viejo = C.execute("SELECT MIN(id) FROM mensajes").fetchone()[0]
ok(total() > tope, f"(ahora el chat ocupa {total() // 1024} KB y el tope es {tope // 1024} KB)")
limpio()
cod, d = enviar(BETO, ANA, "el que dispara el recorte", G + 20)
nuevo_id = d.get("mensaje", {}).get("id")
ok(cod == 200 and total() <= tope, f"al pasarlo, borra hasta quedar debajo ({total() // 1024} KB ≤ {tope // 1024} KB)")
ok(C.execute("SELECT MIN(id) FROM mensajes").fetchone()[0] > viejo, "se fueron los MÁS VIEJOS")
ok(C.execute("SELECT texto FROM mensajes WHERE id = ?", (nuevo_id,)).fetchone() is not None, "⟲ el recién enviado queda")
ok(abs(S._tam["bytes"] - total()) < 1, "la cuenta que lleva el server coincide con la base")
for i in range(300):                                       # una avalancha: el tope aguanta
    limpio()
    enviar(BETO if i % 2 else CARO, ANA, f"avalancha {i} " + "x" * 480, G + 30 + i * 2)
ok(total() <= tope, f"300 mensajes largos más: sigue debajo del tope ({total() // 1024} KB)")
os.environ.pop("R2_CHAT_TOPE_MB")

print("8 · pedidos de amistad")
limpio()
otros = [cuenta(f"otro_g{i}") for i in range(S.FRENO_PEDIR[0] + 1)]
res = [S.pedir(P, BETO[1], str(o[0]), ahora=G + 5000 + i)[0] for i, o in enumerate(otros)]
ok(res[:S.FRENO_PEDIR[0]] == [200] * S.FRENO_PEDIR[0] and res[-1] == 429, f"30 pedidos en la hora; el 31.º, 429 ({res[-1]})")
cod, _ = S.pedir(P, BETO[1], str(otros[-1][0]), ahora=G + 5000 + 3601)
ok(cod == 200, "⟲ a la hora siguiente, puede pedir de nuevo")

P.cerrar_conexiones()
print()
print(("✘ %d FALLAS" % len(fallos)) if fallos else "✔ todo bien")
sys.exit(1 if fallos else 0)
