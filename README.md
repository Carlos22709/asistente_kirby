# Kirby Assistant

Aplicación móvil de asistencia personal para administrar tareas, agenda,
ingresos, gastos, flujo de caja, presupuestos, obligaciones y metas de ahorro.
El cliente Expo consume una API REST FastAPI cuyo orquestador usa function
calling para delegar solicitudes a los agentes de Secretaría, Finanzas o ambos.
Un webhook protegido también puede convertir notificaciones bancarias en gastos
de forma automática.

## Arquitectura

```text
Expo / React Native  →  HTTP + JSON  →  FastAPI  →  SQLAlchemy
                                                        ↓
                                           PostgreSQL local / Supabase
                                           ↓
                                  Ollama / llama3.2
```

El repositorio separa las responsabilidades en dos aplicaciones:

- `mobile/`: cliente Expo/React Native. `app/` contiene las pantallas,
  `components/` los controles reutilizables y `services/` encapsula API,
  almacenamiento seguro y notificaciones locales.
- `backend/`: API FastAPI. `routes/` expone HTTP, `schemas/` valida los
  contratos, `services/` contiene la lógica de negocio y los agentes, y
  `models/` define la persistencia SQLAlchemy.
- Ollama se ejecuta localmente para decidir el agente y estructurar comandos;
  PostgreSQL local o Supabase conserva los datos; Gmail es una integración
  opcional y nunca se consulta directamente desde el teléfono.

En el flujo de voz, el cliente graba el audio, el backend lo transcribe con
Whisper y el orquestador selecciona Secretaría, Finanzas o ambos. La respuesta
regresa al móvil y puede reproducirse mediante síntesis de voz.

Las tablas faltantes se crean automáticamente al arrancar el backend. Los
cambios de esquema para bases existentes se versionan en `backend/migrations/`.
La migración `001_add_gmail_task_reference.sql` incorpora la tabla
`gmail_thread_references` y la relación opcional
`tasks.source_gmail_thread_ref_id -> gmail_thread_references.id`.

El agente de Secretaría también puede trabajar con Gmail: lista, busca y
prioriza mensajes, resume hilos con Ollama, crea borradores y los envía
únicamente después de una confirmación explícita. Gmail continúa siendo la
fuente principal de los correos; la base de datos conserva solamente el
identificador mínimo de un hilo cuando se vincula con una tarea.

## Requisitos

- Node.js 22.13 o posterior y npm.
- Python 3.11 o posterior.
- PostgreSQL 15 o posterior para desarrollo local, o un proyecto de Supabase.
- Ollama 0.34 o posterior y el modelo local `llama3.2`.
- Expo Go en el teléfono, o un emulador Android/iOS.
- Teléfono y computador en la misma red para probar en un dispositivo físico.

Verificación de requisitos:

```powershell
node --version
npm --version
python --version
psql --version
pg_isready
ollama --version
ollama list
```

## 1. Configurar la base de datos

La primera versión del proyecto se desarrolló con PostgreSQL local. Más
adelante se integró Supabase para disponer de persistencia remota. Las dos
modalidades siguen soportadas: FastAPI usa SQLAlchemy y selecciona la base
únicamente mediante `DATABASE_URL`, por lo que el cliente móvil y la lógica de
los agentes no cambian al alternar entre ellas.

### Opción A: PostgreSQL local

Crear el usuario y la base desde una sesión administrativa de `psql`:

```sql
CREATE USER kirby_user WITH PASSWORD 'elige_una_clave_segura';
CREATE DATABASE kirby OWNER kirby_user;
```

La contraseña se configura únicamente en `backend/.env`, archivo excluido de
Git. El ejemplo usa el puerto `5433`; puede cambiarse por el puerto de la
instalación disponible.

### Opción B: Supabase

La app móvil no se conecta directamente a Supabase. Expo continúa llamando a
FastAPI y el backend conecta a PostgreSQL en Supabase. Así, toda la lógica de los
agentes y las credenciales permanecen en el backend; no hace falta instalar el
SDK de Supabase ni guardar una clave pública en el cliente móvil.

1. Crear un proyecto en Supabase y conservar la contraseña de la base de datos.
2. Abrir **Connect > Session pooler** y copiar la URI del puerto `5432`.
   Sustituir `[YOUR-PASSWORD]`; los caracteres especiales de la contraseña
   deben codificarse para una URL.
3. Ejecutar desde la raíz del repositorio:

   ```powershell
   .\scripts\configure-supabase.ps1
   ```

   La URI se solicita de forma oculta, se guarda en archivos excluidos de Git y
   se añade `sslmode=require`.
4. Crear las tablas vacías y comprobar la conexión:

   ```powershell
   .\scripts\initialize-database.ps1
   ```

5. Para copiar datos existentes desde PostgreSQL local, mantener vacío el
   proyecto de Supabase y ejecutar:

   ```powershell
   .\scripts\migrate-to-supabase.ps1
   ```

   El script pide escribir `MIGRAR`, copia todas las tablas y reajusta sus
   secuencias. Se cancela si detecta datos previos en Supabase para no duplicarlos.

La base activa puede alternarse en cualquier momento; después del cambio se
debe reiniciar el backend:

```powershell
.\scripts\switch-database.ps1 -Target Supabase
.\scripts\switch-database.ps1 -Target Local
```

Al inicializar o migrar, el proyecto activa RLS en sus tablas y revoca el acceso
de los roles `anon` y `authenticated`. FastAPI sigue accediendo mediante la
conexión privada de PostgreSQL. Supabase mueve la base a la nube, pero FastAPI y
Ollama continúan ejecutándose en el computador; el iPhone todavía necesita
Tailscale para alcanzar la API fuera de la red local.

## 2. Iniciar el backend

Crear el entorno virtual desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Configurar `backend/.env` con la base seleccionada y dos secretos diferentes:

```dotenv
DATABASE_URL=postgresql+psycopg://kirby_user:elige_una_clave_segura@localhost:5433/kirby
CORS_ORIGINS=*
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
LLM_TIMEOUT_SECONDS=30
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
APP_API_TOKEN=elige_un_secreto_aleatorio_de_al_menos_24_caracteres
BANK_WEBHOOK_TOKEN=elige_un_secreto_aleatorio_de_al_menos_24_caracteres
GMAIL_CLIENT_SECRETS_FILE=credentials/gmail_client_secret.json
GMAIL_TOKEN_FILE=credentials/gmail_token.json
```

`APP_API_TOKEN` protege la API utilizada por el cliente móvil y
`BANK_WEBHOOK_TOKEN` protege exclusivamente el webhook bancario. No deben
tener el mismo valor ni publicarse. Para generar valores aleatorios en
PowerShell puede ejecutarse dos veces:

```powershell
[guid]::NewGuid().ToString("N")
```

Descargar el modelo de Ollama una sola vez y verificar que aparezca en la lista:

```powershell
ollama pull llama3.2
ollama list
```

### Conectar Gmail

La integración es opcional y su autorización se realiza una sola vez:

1. Crear o seleccionar un proyecto en Google Cloud, habilitar **Gmail API** y
   configurar la pantalla de consentimiento OAuth.
2. Crear un cliente OAuth de tipo **Aplicación de escritorio**. En modo de
   prueba, registrar como usuario de prueba la cuenta que autorizará el acceso.
3. Descargar el JSON como
   `backend/credentials/gmail_client_secret.json`.
4. Ejecutar desde la raíz:

   ```powershell
   .\scripts\connect-gmail.ps1
   ```

5. Iniciar sesión en Google y autorizar la lectura de correos y la
   administración de borradores y envíos.

La autorización queda en `backend/credentials/gmail_token.json`. Toda la
carpeta está excluida de Git y no debe compartirse. La aplicación primero crea
un borrador y solo lo envía después de una confirmación explícita como
`Sí, envía el borrador` dentro de la misma conversación.

Iniciar FastAPI:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

- `--host 0.0.0.0` escucha en las interfaces de red del computador y permite el acceso desde el teléfono.
- `--port 3000` expone la API en el puerto 3000.
- `--reload` reinicia el servidor al cambiar código y solo debe usarse durante desarrollo.

La configuración de ejemplo reserva el puerto `5433` para PostgreSQL local.
Si la instalación utiliza `5432` u otro puerto, se debe ajustar
`DATABASE_URL`. Supabase utiliza la URI completa entregada por su panel.

Swagger queda disponible en `http://127.0.0.1:3000/docs` y el estado básico
en `http://127.0.0.1:3000/health`. Al iniciar se crean, si aún no existen,
`tasks`, `incomes`, `expenses`, `budgets`, `financial_accounts`,
`savings_goals`, `events`, `recurring_transactions`, `bank_notifications` y
`gmail_thread_references`, sin borrar datos existentes.

### CORS

`CORS_ORIGINS=*` es práctico en desarrollo local. Para restringirlo, se debe indicar una lista separada por comas, por ejemplo:

```dotenv
CORS_ORIGINS=http://localhost:8081,http://192.168.1.10:8081
```

El comodín no debe utilizarse en un despliegue accesible desde Internet.

## 3. Iniciar la aplicación móvil

En otra terminal, instalar las dependencias del cliente desde la raíz:

```powershell
cd mobile
npm install
npx expo install --fix
Copy-Item .env.example .env
```

Obtener la IPv4 del computador:

```powershell
ipconfig
```

Configurar `mobile/.env` con esa dirección:

```dotenv
EXPO_PUBLIC_API_URL=http://192.168.1.10:3000
```

Después del primer inicio, la pantalla **Configuración** permite verificar la
URL e ingresar el mismo valor de `APP_API_TOKEN` definido en
`backend/.env`. El token se conserva en el almacenamiento seguro del
dispositivo y no forma parte del repositorio.

Iniciar Expo:

```powershell
npx expo start
```

### Inicio rápido en Windows

Una instalación que ya tenga dependencias y variables configuradas puede
arrancarse con un solo comando:

```powershell
cd RUTA\DEL\REPOSITORIO
.\scripts\start-all.ps1
```

El script comprueba las dependencias, levanta Ollama si hace falta, inicia FastAPI y abre Expo en terminales separadas para conservar los logs y el código QR. Para diagnosticar la instalación sin iniciar procesos:

```powershell
.\scripts\start-all.ps1 -CheckOnly
```

El cliente móvil se inicia explícitamente en modo Expo Go. La prueba en un
dispositivo físico requiere instalar **Expo Go** y escanear desde esa aplicación
el QR generado por Metro. No se necesita una cuenta Apple Developer.

El control por voz funciona así:

1. Un toque en el micrófono inicia la grabación.
2. Un segundo toque la detiene.
3. El teléfono envía el audio al backend por Tailscale.
4. Whisper lo transcribe localmente y Kirby procesa el texto con el orquestador multiagente.

El modelo gratuito `base` de Whisper se descarga la primera vez y queda guardado en el computador. Puede cambiarse con `WHISPER_MODEL`, `WHISPER_DEVICE` y `WHISPER_COMPUTE_TYPE` en `backend/.env`.

Los servicios también pueden iniciarse manualmente desde dos terminales:

```powershell
cd RUTA\DEL\REPOSITORIO
.\scripts\start-backend.ps1
```

```powershell
cd RUTA\DEL\REPOSITORIO
.\scripts\start-mobile.ps1
```

Para detener PostgreSQL después de cerrar el backend:

```powershell
.\scripts\stop-postgres.ps1
```

### Acceso remoto con Tailscale

Tailscale es obligatorio para la demostración mediante datos móviles. Debe
instalarse en el computador y el teléfono, usando la misma cuenta en ambos
dispositivos. El estado se verifica con:

```powershell
.\scripts\tailscale-status.ps1
.\scripts\tailscale-status.ps1 -TestBackend
```

Cuando Tailscale está conectado, `start-mobile.ps1` configura temporalmente la API y Metro con la IP privada `100.x`; `phone-webhook.ps1` también la prefiere para Atajos. Si Tailscale no está disponible, ambos conservan el comportamiento de red local. No se abre ningún puerto público ni se usa Funnel.

El QR se abre con Expo Go para probar la aplicación completa. El dictado usa
`expo-audio`, incluido en Expo Go, y envía el archivo a
`POST /assistant/transcribe`; no requiere una development build. En un
teléfono físico, `localhost` apunta al propio teléfono, no al computador, por
eso el script configura la IP privada de Tailscale.

Después de cambiar una variable `EXPO_PUBLIC_*` se debe reiniciar Expo. Para
limpiar una configuración anterior de Metro:

```powershell
npx expo start --clear
```

## Uso

- **Inicio:** muestra tareas pendientes y próximas, gasto diario/semanal, siguiente evento y presupuesto del mes.
- **Tareas:** permite crear, editar, iniciar, pausar, completar, reabrir, filtrar y eliminar tareas con estados Pendiente, En progreso y Completada. Las vencidas tienen tratamiento visual distinto.
- **Finanzas:** permite registrar ingresos y gastos, calcular el flujo neto mensual, administrar el presupuesto, controlar tarjetas o préstamos y seguir metas de ahorro con aportes y porcentaje de avance.
- **Agenda:** permite crear, editar, agrupar por fecha, filtrar y eliminar eventos próximos.
- **Recordatorios:** una tarea o evento futuro puede programar un recordatorio local. La app conserva su identificador en el dispositivo, lo reemplaza al editar, lo cancela al desactivarlo, eliminar el elemento o completar una tarea, y evita duplicados. Si el permiso se deniega, el resto de la app sigue funcionando. No se usan notificaciones push.
- **Asistente:** la pestaña móvil acepta texto o dictado en español, conserva hasta 20 mensajes de contexto y puede leer la respuesta en voz alta. `POST /assistant/chat` usa un primer function calling para elegir Secretaría, Finanzas o ambos, y un segundo para seleccionar la acción de dominio. Secretaría consulta o crea tareas y eventos; también lista, busca, prioriza y resume Gmail, crea borradores y solo los envía con confirmación explícita. Finanzas consulta el estado financiero o registra gastos. Las acciones locales se guardan inmediatamente en PostgreSQL.
- **Registro bancario automático:** `POST /webhooks/bank-transactions` recibe el texto de una notificación bancaria, Ollama extrae la transacción y la registra como gasto. El texto se trata como contenido no confiable, se ignoran códigos, promociones, saldos y operaciones rechazadas, y una huella evita registrar dos veces la misma notificación. Por seguridad, solo COP se registra automáticamente; otras monedas quedan para revisión manual.

Los campos de fecha usan `AAAA-MM-DD` y los de fecha/hora `AAAA-MM-DDTHH:mm`, por ejemplo `2026-09-10T15:00`. La presentación y los cálculos diarios usan `America/Bogota`.

Ejemplo desde PowerShell, con FastAPI iniciado:

```powershell
$body = @{
  message = "¿Cuánto dinero me queda y qué tareas vencen esta semana?"
  history = @()
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:3000/assistant/chat `
  -ContentType "application/json" `
  -Body $body
```

Ejemplo de una automatización bancaria desde PowerShell. La clave se lee de `backend/.env` y no se imprime:

```powershell
$token = (Get-Content backend\.env |
  Where-Object { $_ -like "BANK_WEBHOOK_TOKEN=*" }).Split("=", 2)[1]
$body = @{
  text = "Compra aprobada por `$45.900 en MERCADO CAMPUS hoy. Ref ABC123."
  source = "android_notification_listener"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:3000/webhooks/bank-transactions `
  -Headers @{ "X-Webhook-Token" = $token } `
  -ContentType "application/json" `
  -Body $body
```

La respuesta usa `created` si creó el gasto, `duplicate` si ya había procesado ese mismo texto, o `ignored` si no detectó una transacción válida. En un teléfono, Tasker/MacroDroid (Android) o una automatización de Atajos (iOS) deben enviar el texto recibido con ese mismo encabezado. `BANK_WEBHOOK_TOKEN` no debe publicarse ni incluirse en el código de la app.

La configuración de un iPhone —y la alternativa equivalente en Android— se
encuentra en [la guía de automatización del teléfono](docs/automatizacion-telefono.md).
El ayudante `scripts/phone-webhook.ps1` muestra la URL local, copia la clave
sin imprimirla y prueba la conexión sin crear gastos.

## Endpoints

| Área | Endpoints principales |
|---|---|
| Sistema | `GET /health`, `GET /docs` |
| Asistente | `POST /assistant/chat` |
| Automatización bancaria | `GET /webhooks/bank-transactions/status`, `POST /webhooks/bank-transactions` |
| Inicio | `GET /dashboard/summary` |
| Tareas | `GET/POST /tasks`, `GET/PUT/DELETE /tasks/{id}`, `PATCH /tasks/{id}/status`, `PATCH /tasks/{id}/complete` (compatibilidad) |
| Gastos | `GET/POST /expenses`, `GET/PUT/DELETE /expenses/{id}`, `GET /expenses/summary` |
| Ingresos y flujo | `GET/POST /incomes`, `GET/PUT/DELETE /incomes/{id}`, `GET /incomes/cash-flow` |
| Tarjetas y préstamos | `GET/POST /financial-accounts`, `GET/PUT/DELETE /financial-accounts/{id}`, `GET /financial-accounts/summary` |
| Metas de ahorro | `GET/POST /savings-goals`, `GET/PUT/DELETE /savings-goals/{id}`, `POST /savings-goals/{id}/contributions`, `GET /savings-goals/summary` |
| Presupuestos | `GET/POST /budgets`, `GET /budgets/current`, `PUT/DELETE /budgets/{id}` |
| Agenda | `GET/POST /events`, `GET/PUT/DELETE /events/{id}` |

Swagger documenta filtros y cuerpos exactos. La API usa `201` al crear, `204` al eliminar, `404` para recursos inexistentes, `409` al duplicar un presupuesto mensual y `422` para datos inválidos.

## Verificación recomendada

Con PostgreSQL y FastAPI iniciados:

1. Confirmar `GET /health` y abrir `/docs`.
2. Desde Swagger, crear, listar, editar, completar/reabrir y eliminar una tarea.
3. Crear, editar y eliminar un gasto; revisar `/expenses/summary`.
4. Crear el presupuesto del mes y revisar `/budgets/current`; repetirlo para
   confirmar la respuesta `409`.
5. Crear, editar, filtrar y eliminar un evento.
6. Probar `/assistant/chat` con una consulta de agenda, una financiera y otra
   que combine ambos dominios.
7. Con Gmail conectado, solicitar correos no leídos, buscar uno, resumir su hilo
   y crear un borrador. Confirmar que no se envía hasta responder
   `Sí, envía el borrador`.
8. Enviar una notificación de compra al webhook con su token; repetirla y
   confirmar que la segunda respuesta sea `duplicate` y no cree otro gasto.
9. Enviar montos negativos, títulos vacíos, mes `13` y una fecha final anterior
   para confirmar respuestas `422`.
10. Reiniciar Uvicorn y volver a listar los recursos para comprobar persistencia.
11. En `mobile`, ejecutar:

   ```powershell
   npm run typecheck
   npx expo-doctor@latest
   ```

12. Abrir la app, realizar un CRUD en cada sección y confirmar que listas,
    totales e Inicio cambian al volver a cada pestaña.

La prueba automatizada del contrato HTTP usa una base SQLite temporal únicamente para aislar el test; la aplicación real sigue configurada para PostgreSQL:

```powershell
cd backend
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

## Estructura

```text
backend/
  app/
    models/       # tablas SQLAlchemy
    schemas/      # entrada, validación y respuesta Pydantic
    routes/       # API REST
    services/     # cálculos de negocio, cliente Ollama y orquestador
    database.py
    main.py
  tests/          # pruebas unitarias e integrales
mobile/
  app/(tabs)/     # Inicio, Tareas, Finanzas y Agenda
  components/     # controles visuales reutilizables
  services/       # fetch centralizado y recursos de la API
  types/
  utils/
docs/             # automatización bancaria desde el teléfono
scripts/          # configuración, diagnóstico e inicio del entorno
```

## Solución de problemas

- **`connection refused` en FastAPI:** verificar que PostgreSQL esté iniciado y
  que `DATABASE_URL` use el puerto local correcto. Con Supabase, verificar la
  URI de **Session pooler**, el puerto `5432`, la contraseña y
  `sslmode=require`.
- **Supabase rechaza la conexión:** comprobar que el proyecto no esté pausado y
  copiar nuevamente la URI desde **Connect > Session pooler**. La URI no debe
  publicarse ni compartirse.
- **Ollama no tiene el modelo:** ejecutar `ollama pull llama3.2`; `ollama list`
  debe mostrarlo antes de usar `/assistant/chat`.
- **Gmail no está conectado:** confirmar que existan ambos JSON dentro de
  `backend/credentials/`; si falta el token, ejecutar
  `scripts/connect-gmail.ps1` nuevamente.
- **Google muestra “acceso bloqueado”:** verificar que Gmail API esté habilitada,
  que el cliente sea de tipo aplicación de escritorio y que la cuenta esté
  registrada como usuario de prueba.
- **El webhook responde `401`:** comprobar que `X-Webhook-Token` coincida
  exactamente con `BANK_WEBHOOK_TOKEN` en `backend/.env`.
- **El webhook responde `503`:** confirmar la configuración de la clave y el
  estado de Ollama; reiniciar FastAPI después de cambiar `.env`.
- **La descarga de Ollama se interrumpe:** ejecutar nuevamente
  `ollama pull llama3.2`; las capas completas se reutilizan. Ante fallos
  repetidos contra `cloudflarestorage.com`, revisar VPN, proxy, antivirus o
  firewall.
- **La app no llega a la API:** abrir
  `http://IP_DEL_COMPUTADOR:3000/health` desde el teléfono. Si no responde,
  revisar IP, Wi-Fi, firewall y `--host 0.0.0.0`.
- **Error de dependencias Expo:** verificar una versión compatible de Node. Si
  es necesario, eliminar únicamente `mobile/node_modules`, ejecutar
  `npm install` y luego `npx expo install --fix`.
- **Puerto ocupado:** detener el proceso que use el puerto 3000. Cualquier
  cambio de puerto requiere actualizar también `EXPO_PUBLIC_API_URL`.
