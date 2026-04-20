<%@page contentType="text/html" pageEncoding="UTF-8"%>
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ByteBeat — Login</title>

    <link
      href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
      rel="stylesheet"
      integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
      crossorigin="anonymous"
    />

    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
    />

    <style>
      :root {
        --wood-ebony: #0b0b0c;
        --wood-walnut: #5b371b;
        --wood-teak: #9c6b3d;
        --wood-maple: #d6a67a;
        --wood-amber: #f6b26b;
      }

      html, body {
        height: 100%;
      }

      body {
        background:
          repeating-linear-gradient(
            33deg,
            rgba(91, 57, 29, 0.26) 0px,
            rgba(91, 57, 29, 0.26) 3px,
            rgba(48, 28, 14, 0.26) 3px,
            rgba(48, 28, 14, 0.26) 6px
          ),
          radial-gradient(
            1200px 600px at 15% -20%,
            rgba(214, 166, 122, 0.22),
            transparent
          ),
          radial-gradient(
            1000px 500px at 90% 110%,
            rgba(153, 98, 59, 0.28),
            transparent
          ),
          linear-gradient(180deg, var(--wood-ebony) 0%, #0a0a0a 55%, #0e0e0f 100%);
        color: #f2f2f2;
      }

      .hero-wood {
        position: relative;
        overflow: hidden;
        background:
          repeating-linear-gradient(
            40deg,
            rgba(97, 61, 32, 0.22) 0px,
            rgba(97, 61, 32, 0.22) 3px,
            rgba(54, 33, 17, 0.22) 3px,
            rgba(54, 33, 17, 0.22) 6px
          ),
          radial-gradient(
            1000px 420px at 10% 0%,
            rgba(214, 166, 122, 0.25),
            transparent
          ),
          radial-gradient(
            900px 420px at 90% 100%,
            rgba(156, 107, 61, 0.27),
            transparent
          ),
          linear-gradient(180deg, #0a0a0a 0%, #0a0a0a 60%, #0e0e0f 100%);
      }

      .hero-wood::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(
          to bottom,
          rgba(0, 0, 0, 0.25),
          transparent 40%,
          rgba(0, 0, 0, 0.6)
        );
      }

      .card-glass {
        background: rgba(18, 18, 18, 0.78);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 1.25rem;
        backdrop-filter: blur(8px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
      }

      .btn-wood {
        background-image: linear-gradient(
          to bottom,
          var(--wood-maple),
          var(--wood-teak),
          var(--wood-walnut)
        );
        color: #0b0b0c;
        border: 0;
      }

      .btn-wood:hover {
        filter: brightness(1.08);
      }

      .btn-google {
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.06);
        color: #fff;
      }

      .btn-google:hover {
        background: rgba(255, 255, 255, 0.12);
        color: #fff;
      }

      .form-control,
      .form-check-input {
        background-color: rgba(0, 0, 0, 0.35);
        color: #fff;
        border-color: rgba(255, 255, 255, 0.12);
      }

      .form-control::placeholder {
        color: rgba(255,255,255,.45);
      }

      .form-control:focus {
        background-color: rgba(0, 0, 0, 0.35);
        color: #fff;
        border-color: rgba(246, 178, 107, 0.5);
        box-shadow: 0 0 0 0.25rem rgba(246, 178, 107, 0.2);
      }

      .divider {
        position: relative;
        text-align: center;
      }

      .divider span {
        background: rgba(18, 18, 18, 0.78);
        padding: 0 0.5rem;
        position: relative;
        z-index: 1;
      }

      .divider::before {
        content: "";
        position: absolute;
        inset: 50% 0 auto;
        height: 1px;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 255, 255, 0.12),
          transparent
        );
      }

      .piano {
        --octaves: 2;
        --white-count: calc(var(--octaves) * 7);
        --cols: var(--white-count);
        --w: calc(100% / var(--white-count));
        --h: 190px;
        --bk-w: min(28px, calc(var(--w) * 0.65));
        --bk-h: calc(var(--h) * 0.62);

        position: relative;
        background: linear-gradient(180deg, #2e1f12, #3c2818);
        border-radius: 14px;
        padding: 10px 12px 14px;
        user-select: none;
        box-shadow: 0 20px 40px rgba(0,0,0,.45);
      }

      .white-keys {
        display: grid;
        grid-template-columns: repeat(var(--cols), 1fr);
        gap: 2px;
        height: var(--h);
      }

      .key-white {
        appearance: none;
        background: linear-gradient(#ffffff, #efefef);
        border: 1px solid #c9c9c9;
        border-bottom: 4px solid #a5a5a5;
        border-radius: 0 0 8px 8px;
        box-shadow: inset 0 -12px 0 rgba(0, 0, 0, 0.05);
        width: 100%;
        height: 100%;
        cursor: pointer;
        touch-action: manipulation;
      }

      .key-white:active, .key-white.is-down {
        background: linear-gradient(#f4f4f4, #dddddd);
        border-bottom-color: #888;
        box-shadow: inset 0 -6px 0 rgba(0, 0, 0, 0.06);
      }

      .black-keys {
        position: absolute;
        top: 10px;
        left: 12px;
        right: 12px;
        height: var(--bk-h);
        pointer-events: none;
        z-index: 5;
      }

      .key-black {
        position: absolute;
        width: var(--bk-w);
        height: 100%;
        transform: translateX(-50%);
        background: linear-gradient(#222, #000);
        border: 1px solid #111;
        border-radius: 0 0 6px 6px;
        box-shadow: 0 8px 14px rgba(0, 0, 0, 0.55), inset 0 -8px 0 #111;
        cursor: pointer;
        pointer-events: auto;
        touch-action: manipulation;
        left: calc(var(--w) * var(--i) - var(--w) / 2);
      }

      .key-black:active, .key-black.is-down {
        background: linear-gradient(#333, #111);
        box-shadow: 0 5px 9px rgba(0, 0, 0, 0.55), inset 0 -4px 0 #111;
      }

      .base-wood {
        height: 14px;
        background: linear-gradient(90deg, #3f2a18, #5a3f24, #3f2a18);
        border-radius: 0 0 12px 12px;
      }

      .transport button {
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.06);
        color: #cbd5e1;
      }

      .transport button:hover {
        background: rgba(255, 255, 255, 0.12);
      }

      .transport .play {
        color: #76e2b3;
      }

      .text-soft {
        color: rgba(255,255,255,.72);
      }

      @media (max-width: 991.98px) {
        .hero-side {
          display: none !important;
        }
        .form-side {
          width: 100% !important;
        }
      }
    </style>
  </head>

  <body class="d-flex flex-column">
    <nav
      class="navbar navbar-dark border-bottom border-light-subtle"
      style="background: rgba(0, 0, 0, 0.55); backdrop-filter: blur(6px);"
    >
      <div class="container">
        <div class="d-flex align-items-center">
          <span
            class="d-inline-grid place-items-center rounded-3"
            style="width: 16%; margin-right: 2%;"
          >
            <img
              src="${pageContext.request.contextPath}/logor.png"
              alt="ByteBeat"
              style="width: 100%; height: 100%; object-fit: contain; display: block;"
              draggable="false"
            />
          </span>
          <strong class="text-white">ByteBeat</strong>
        </div>
        <small class="text-white-50 d-none d-md-block">
          Generador de acompañamiento • Modo oscuro madera
        </small>
      </div>
    </nav>

    <main class="container-fluid flex-fill">
      <div class="row min-vh-100">
        <section
          class="hero-wood hero-side d-none d-lg-flex flex-column justify-content-between p-5"
          style="width: 60%;"
        >
          <div class="position-relative" style="z-index: 1;">
            <h1 class="display-5 fw-semibold text-white">
              Inspírate, aprende, visualiza y crea
              <span style="color: var(--wood-amber) !important;">
                en un mismo lugar
              </span>
            </h1>
            <p class="mt-3 text-soft" style="max-width: 40ch;">
              Sube tu melodía y deja que
              <span class="fw-medium" style="color: var(--wood-amber);">
                ByteBeat
              </span>
              cree el acompañamiento armónico y rítmico con sensibilidad musical.
            </p>
          </div>

          <div class="position-relative" style="z-index: 1;">
            <div
              class="piano shadow-lg position-relative"
              data-octaves="2"
              data-start-octave="4"
            >
              <div class="white-keys"></div>
              <div class="black-keys"></div>
              <div class="base-wood mt-3"></div>
            </div>
          </div>
        </section>

        <section
          class="form-side d-flex align-items-center justify-content-center py-5"
          style="width: 40%;"
        >
          <div class="w-100" style="max-width: 440px;">
            <div class="card card-glass p-4 p-md-5">
              <h2 class="text-center text-white">Inicia sesión</h2>
              <p class="text-center text-white-50 mb-4">
                Accede para generar acompañamientos personalizados
              </p>

              <%
                String error = (String) request.getAttribute("error");
                String mensaje = (String) request.getAttribute("mensaje");
              %>

              <% if (error != null) { %>
                <div class="alert alert-danger" role="alert">
                  <%= error %>
                </div>
              <% } %>

              <% if (mensaje != null) { %>
                <div class="alert alert-success" role="alert">
                  <%= mensaje %>
                </div>
              <% } %>

              <form
                id="loginForm"
                class="needs-validation"
                novalidate
                action="${pageContext.request.contextPath}/LoginServlet"
                method="post"
              >
                <div class="mb-3">
                  <label for="username" class="form-label text-white-50">
                    Usuario
                  </label>
                  <input
                    type="text"
                    class="form-control"
                    id="username"
                    name="username"
                    placeholder="Tu usuario"
                    required
                  />
                  <div class="invalid-feedback text-white-50">
                    Ingresa tu usuario.
                  </div>
                </div>

                <div class="mb-2">
                  <label for="password" class="form-label text-white-50">
                    Contraseña
                  </label>
                  <div class="input-group has-validation">
                    <input
                      type="password"
                      class="form-control"
                      id="password"
                      name="password"
                      placeholder="••••••••"
                      minlength="6"
                      required
                    />
                    <button
                      type="button"
                      class="btn btn-outline-light toggle-password text-white-50"
                      tabindex="-1"
                      aria-label="Mostrar u ocultar contraseña"
                      style="border-color: rgba(255, 255, 255, 0.12); background: rgba(255, 255, 255, 0.06);"
                    >
                      <i class="bi bi-eye"></i>
                    </button>
                    <div class="invalid-feedback">
                      La contraseña debe tener al menos 6 caracteres.
                    </div>
                  </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mb-3">
                  <div class="form-check">
                    <input
                      class="form-check-input"
                      type="checkbox"
                      id="remember"
                      name="remember"
                    />
                    <label class="form-check-label text-white-50" for="remember">
                      Recuérdame
                    </label>
                  </div>
                  <a
                    href="#"
                    class="link-light link-underline-opacity-0 link-underline-opacity-100-hover"
                  >
                    ¿Olvidaste tu contraseña?
                  </a>
                </div>

                <button class="btn btn-wood w-100 py-2" type="submit">
                  Entrar
                </button>

                <div class="divider my-3">
                  <span class="text-white-50">o</span>
                </div>

                <!-- Preparado para Google Login -->
                <button
                  type="button"
                  id="googleLoginBtn"
                  class="btn btn-google w-100 py-2"
                  data-google-auth="pending"
                >
                  <i class="bi bi-google me-2"></i>
                  Continuar con Google
                </button>

                <!-- Campo preparado para recibir token o credencial Google después -->
                <input type="hidden" id="googleCredential" name="googleCredential" value="" />

                <p class="text-center text-white-50 mt-3 mb-0">
                  ¿No tienes cuenta?
                  <a
                    href="${pageContext.request.contextPath}/registro.jsp"
                    class="link-warning link-underline-opacity-0"
                  >
                    Crear cuenta
                  </a>
                </p>
              </form>
            </div>

            <div class="transport d-flex justify-content-center gap-2 mt-4">
              <button class="btn btn-sm" aria-label="Anterior" type="button">
                <i class="bi bi-skip-backward-fill"></i>
              </button>
              <button class="btn btn-sm play" aria-label="Reproducir" type="button">
                <i class="bi bi-play-fill"></i>
              </button>
              <button class="btn btn-sm" aria-label="Siguiente" type="button">
                <i class="bi bi-skip-forward-fill"></i>
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>

    <script
      src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
      integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
      crossorigin="anonymous"
    ></script>

    <script>
      (() => {
        const piano = document.querySelector(".piano");
        if (!piano) return;

        const whiteWrap = piano.querySelector(".white-keys");
        const blackWrap = piano.querySelector(".black-keys");

        const OCTAVES = Math.max(1, Math.min(3, parseInt(piano.dataset.octaves || "2", 10)));
        const START_OCT = parseInt(piano.dataset.startOctave || "4", 10);
        const TUNING_A4 = 440;

        piano.style.setProperty("--octaves", OCTAVES);
        piano.style.setProperty("--white-count", OCTAVES * 7);
        piano.style.setProperty("--cols", OCTAVES * 7);

        whiteWrap.innerHTML = "";
        blackWrap.innerHTML = "";

        const whites = ["C", "D", "E", "F", "G", "A", "B"];
        const blacks = ["C#", "D#", null, "F#", "G#", "A#", null];

        for (let o = 0; o < OCTAVES; o++) {
          const octaveNum = START_OCT + o;

          whites.forEach((name) => {
            const btn = document.createElement("button");
            btn.className = "key-white";
            btn.type = "button";
            btn.dataset.note = `${name}${octaveNum}`;
            whiteWrap.appendChild(btn);
          });

          blacks.forEach((bName, idx) => {
            if (!bName) return;
            const btn = document.createElement("button");
            btn.className = "key-black";
            btn.type = "button";
            btn.dataset.note = `${bName}${octaveNum}`;
            const i = o * 7 + (idx + 1);
            btn.style.setProperty("--i", i);
            blackWrap.appendChild(btn);
          });
        }

        let audioCtx = null;
        const getCtx = () => {
          if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          if (audioCtx.state === "suspended") audioCtx.resume();
          return audioCtx;
        };

        const SEMI = { C:0,"C#":1,D:2,"D#":3,E:4,F:5,"F#":6,G:7,"G#":8,A:9,"A#":10,B:11 };

        function noteToFreq(n) {
          const m = /^([A-G])(#?)(-?\d+)$/.exec(n);
          if (!m) return null;
          const base = m[1] + m[2];
          const oct = parseInt(m[3], 10);
          const midi = (oct + 1) * 12 + SEMI[base];
          return TUNING_A4 * Math.pow(2, (midi - 69) / 12);
        }

        function createVoice(freq) {
          const ctx = getCtx();
          const now = ctx.currentTime;

          const osc = ctx.createOscillator();
          const gain = ctx.createGain();

          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, now);

          const A = 0.01, D = 0.18, S = 0.001, R = 0.25, MAXLEN = 2.5;

          gain.gain.setValueAtTime(0.0001, now);
          gain.gain.linearRampToValueAtTime(1.0, now + A);
          gain.gain.linearRampToValueAtTime(S, now + A + D);

          osc.connect(gain).connect(ctx.destination);
          osc.start(now);
          osc.stop(now + MAXLEN);

          let ended = false;
          osc.onended = () => (ended = true);

          return {
            release() {
              if (ended) return;
              const t = ctx.currentTime;
              gain.gain.cancelScheduledValues(t);
              const current = Math.max(0.0001, gain.gain.value);
              gain.gain.setValueAtTime(current, t);
              gain.gain.linearRampToValueAtTime(0.0001, t + R);
            },
          };
        }

        const press = (el) => el.classList.add("is-down");
        const releaseVis = (el) => el.classList.remove("is-down");

        const allKeys = piano.querySelectorAll(".key-white, .key-black");
        allKeys.forEach((k) => {
          k._voices = Object.create(null);

          k.addEventListener("pointerdown", (e) => {
            e.preventDefault();
            const f = noteToFreq(k.dataset.note);
            if (!f) return;
            const v = createVoice(f);
            k._voices[e.pointerId] = v;
            press(k);
            try { k.setPointerCapture(e.pointerId); } catch {}
          });

          const endFor = (e) => {
            const v = k._voices && k._voices[e.pointerId];
            if (v) {
              v.release();
              delete k._voices[e.pointerId];
            }
            if (!k._voices || Object.keys(k._voices).length === 0) releaseVis(k);
          };

          k.addEventListener("pointerup", endFor);
          k.addEventListener("pointercancel", endFor);
        });
      })();

      (() => {
        "use strict";
        const form = document.getElementById("loginForm");

        form.addEventListener("submit", (event) => {
          if (!form.checkValidity()) {
            event.preventDefault();
            event.stopPropagation();
          }
          form.classList.add("was-validated");
        }, false);
      })();

      (() => {
        const btn = document.querySelector(".toggle-password");
        const input = document.getElementById("password");

        if (!btn || !input) return;

        btn.addEventListener("click", () => {
          const isText = input.getAttribute("type") === "text";
          input.setAttribute("type", isText ? "password" : "text");
          btn.querySelector("i").className = isText
            ? "bi bi-eye"
            : "bi bi-eye-slash";
        });
      })();

      (() => {
        const googleBtn = document.getElementById("googleLoginBtn");
        const googleCredential = document.getElementById("googleCredential");

        if (!googleBtn) return;

        googleBtn.addEventListener("click", () => {
          // Placeholder para integrar Google Sign-In después
          // Aquí luego vas a abrir el flujo real de autenticación Google.
          googleCredential.value = "";
          alert("Botón de Google preparado. El siguiente paso será conectar la autenticación real.");
        });
      })();
    </script>
  </body>
</html>