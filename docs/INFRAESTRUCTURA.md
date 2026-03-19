# SISMO — Infraestructura de Producción RODDOS S.A.S.
## Stack
| Componente | Plataforma | Plan |
|---|---|---|
| Frontend | Vercel | Hobby |
| Backend | Render | Starter $7/mes |
| Base de datos | MongoDB Atlas | M0 Free |
| Repo | GitHub RoddosColombia/SISMO | Private |
## Reglas de oro
1. Todo cambio pasa por GitHub — nunca editar en Render/Vercel
2. Variables de entorno solo en dashboards, nunca en código
3. init_mongodb_sismo.py siempre actualizado
4. Commits: [BUILD-XX] [FIX] [HOTFIX] [INFRA] [INIT]
## Inicializar MongoDB desde cero
pip install pymongo python-dotenv
MONGO_URL="..." DB_NAME="sismo" python init_mongodb_sismo.py
