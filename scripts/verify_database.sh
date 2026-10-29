#!/usr/bin/env bash
# Verifica contra un PostgreSQL real: migración (dos veces = idempotente), rol de aplicación y aislamiento RLS.
# Uso: PGHOST=… PGPORT=… PGUSER=postgres [PGPASSWORD=…] ./scripts/verify_database.sh   (crea y borra la BD "ci_verify")
set -euo pipefail
cd "$(dirname "$0")/.."
DB=ci_verify; APP_PW=ci-app-pw
MIG=ConjuntoInteligente/src/Persistence/Migrations/0001_initial.sql
psql -v ON_ERROR_STOP=1 -q -d postgres -c "drop database if exists $DB" -c "create database $DB"
for i in 1 2; do psql -v ON_ERROR_STOP=1 -q -d $DB -f "$MIG" 2>&1 | grep -v NOTICE || true; done
echo "OK migración aplicada dos veces"
sed "s/CAMBIAR-ESTA-CLAVE/$APP_PW/; s/ON DATABASE railway/ON DATABASE $DB/" ConjuntoInteligente/infra/postgres/create_app_role.sql | psql -v ON_ERROR_STOP=1 -q -d $DB >/dev/null
A=11111111-1111-1111-1111-111111111111; B=22222222-2222-2222-2222-222222222222
psql -v ON_ERROR_STOP=1 -q -d $DB -c "insert into tenants(id,code,name) values ('$A','a','A'),('$B','b','B')"
app() { PGPASSWORD=$APP_PW psql -U conjunto_app -d $DB -At -v ON_ERROR_STOP=1 "$@"; }
n() { app -c "select set_config('app.tenant_id','$1',false)" -c "select count(*) from residents" | tail -1; }
app -c "select set_config('app.tenant_id','$A',false)" -c "insert into residents(id,tenant_id,name,email,unit) values (gen_random_uuid(),'$A','Ana','a@a.co','101')" >/dev/null
fail=0
[[ "$(n $A)" == 1 ]] && echo "OK tenant A ve su dato" || { echo "FALLA tenant A"; fail=1; }
[[ "$(n $B)" == 0 ]] && echo "OK tenant B no ve datos de A" || { echo "FALLA aislamiento"; fail=1; }
[[ "$(n '')" == 0 ]] && echo "OK sin tenant no ve nada" || { echo "FALLA sin tenant"; fail=1; }
if app -c "select set_config('app.tenant_id','$B',false)" -c "insert into residents(id,tenant_id,name,email,unit) values (gen_random_uuid(),'$A','X','x@a.co','9')" >/dev/null 2>&1; then echo "FALLA insert cruzado permitido"; fail=1; else echo "OK insert entre tenants rechazado"; fi
sup=$(psql -At -d $DB -c "select rolsuper or rolbypassrls from pg_roles where rolname='conjunto_app'")
[[ "$sup" == f ]] && echo "OK rol de aplicación sin superusuario/BYPASSRLS" || { echo "FALLA rol privilegiado"; fail=1; }
psql -q -d postgres -c "drop database $DB"
exit $fail
