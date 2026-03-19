import os, math, uuid
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

client = MongoClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

def primer_mierc(fecha):
    d = datetime.strptime(fecha, '%Y-%m-%d') + timedelta(days=7)
    return d + timedelta(days=(2 - d.weekday()) % 7)

def cronograma(primera, n, valor, modo, pagadas):
    dias = {'semanal':7,'quincenal':14,'mensual':28}.get(modo,7)
    return [{'numero':i+1,'fecha':(primera+timedelta(days=dias*i)).strftime('%Y-%m-%d'),'valor':valor,'estado':'pagada' if i<pagadas else 'pendiente','fecha_pago':(primera+timedelta(days=dias*i)).strftime('%Y-%m-%d') if i<pagadas else None,'metodo_pago':'transferencia' if i<pagadas else None,'alegra_payment_id':None} for i in range(n)]

def sig_codigo():
    u = db.loanbook.find_one({'codigo':{'$regex':'^LB-2026-'}},sort=[('codigo',-1)])
    n = int(u['codigo'].split('-')[-1])+1 if u and u.get('codigo') else 1
    return f'LB-2026-{n:04d}'

LBS=[
    {'cliente_nombre':'CHENIER QUINTERO','cliente_cedula':'1283367','cliente_tipo_doc':'PPT','moto_chasis':'9FL25AF3XVDB95057','moto_motor':'BF3AT13C2338','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT90I','plan':'P52S','modo_pago':'semanal','valor_total':10814800,'cuota_inicial':1460000,'cuota_base':179900,'fecha_factura':'2026-02-25','fecha_entrega':'2026-03-05','cuotas_pagadas':2},
    {'cliente_nombre':'JOSE ALTAMIRANDA','cliente_cedula':'1063146896','cliente_tipo_doc':'CC','moto_chasis':'9FLT81003VDB62413','moto_motor':'RF5AT18A5448','moto_referencia':'SPORT 100','moto_color':'NEGRO AZUL NEBULOSA','moto_placa':'BWT94I','plan':'P78S','modo_pago':'semanal','valor_total':11300000,'cuota_inicial':1160000,'cuota_base':130000,'fecha_factura':'2026-02-25','fecha_entrega':'2026-03-05','cuotas_pagadas':2},
    {'cliente_nombre':'ERNESTO JAIME','cliente_cedula':'6226605','cliente_tipo_doc':'PPT','moto_chasis':'9FL25AF39VDB95048','moto_motor':'BF3AT15C2365','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT91I','plan':'P78S','modo_pago':'semanal','valor_total':13152200,'cuota_inicial':1460000,'cuota_base':149900,'fecha_factura':'2026-02-25','fecha_entrega':'2026-03-05','cuotas_pagadas':2},
    {'cliente_nombre':'RONALDO CARCAMO','cliente_cedula':'1126257783','cliente_tipo_doc':'CC','moto_chasis':'9FL25AF36VDB95055','moto_motor':'BF3AT18C2341','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT92I','plan':'P78S','modo_pago':'semanal','valor_total':13152200,'cuota_inicial':1460000,'cuota_base':149900,'fecha_factura':'2026-02-25','fecha_entrega':'2026-03-05','cuotas_pagadas':2},
    {'cliente_nombre':'BEATRIZ GARCIA','cliente_cedula':'5203668','cliente_tipo_doc':'PPT','moto_chasis':'9FL25AF35VDB95046','moto_motor':'BF3AT13C2568','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT93I','plan':'P78S','modo_pago':'semanal','valor_total':13152200,'cuota_inicial':1460000,'cuota_base':149900,'fecha_factura':'2026-02-26','fecha_entrega':'2026-03-05','cuotas_pagadas':1},
    {'cliente_nombre':'ALEXIS CRESPO','cliente_cedula':'598091','cliente_tipo_doc':'PPT','moto_chasis':'9FL25AF31VDB95058','moto_motor':'BF3AT18C2356','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT95I','plan':'P52S','modo_pago':'semanal','valor_total':10814800,'cuota_inicial':1460000,'cuota_base':179900,'fecha_factura':'2026-02-27','fecha_entrega':'2026-03-05','cuotas_pagadas':2},
    {'cliente_nombre':'MOISES ASCANIO','cliente_cedula':'199053959','cliente_tipo_doc':'PAS','moto_chasis':'9FLT81005VDB62414','moto_motor':'RF5AT1XA5494','moto_referencia':'SPORT 100','moto_color':'NEGRO AZUL NEBULOSA','moto_placa':'BWT96I','plan':'P39S','modo_pago':'quincenal','valor_total':7810000,'cuota_inicial':1160000,'cuota_base':130000,'fecha_factura':'2026-02-26','fecha_entrega':'2026-03-05','cuotas_pagadas':0},
    {'cliente_nombre':'KREISBER CABRICES','cliente_cedula':'7711632','cliente_tipo_doc':'CC','moto_chasis':'9FL25AF3XVDB95043','moto_motor':'BF3AT15C2580','moto_referencia':'RAIDER 125','moto_color':'NEGRO NEBULOSA','moto_placa':'BWT97I','plan':'P39S','modo_pago':'quincenal','valor_total':9440000,'cuota_inicial':1460000,'cuota_base':149900,'fecha_factura':'2026-02-26','fecha_entrega':'2026-03-05','cuotas_pagadas':0},
    {'cliente_nombre':'DORA MARIA OSPINA','cliente_cedula':'20677811','cliente_tipo_doc':'CC','moto_chasis':'9FLT81003VDB62265','moto_motor':'RF5AT15A5593','moto_referencia':'SPORT 100','moto_color':'NEGRO AZUL NEBULOSA','moto_placa':'BWT98I','plan':'P78S','modo_pago':'semanal','valor_total':11300000,'cuota_inicial':1160000,'cuota_base':130000,'fecha_factura':'2026-03-05','fecha_entrega':'2026-03-10','cuotas_pagadas':0},
    {'cliente_nombre':'SINDY BELTRAN','cliente_cedula':'1012415625','cliente_tipo_doc':'CC','moto_chasis':'9FL25AF30VDB95987','moto_motor':'BF3AV14L1853','moto_referencia':'RAIDER 125','moto_color':'SLATE GREEN','moto_placa':'EMO40I','plan':'P52S','modo_pago':'semanal','valor_total':10814800,'cuota_inicial':1460000,'cuota_base':179900,'fecha_factura':'2026-03-16','fecha_entrega':'2026-03-19','cuotas_pagadas':0},
]

MULT   = {'semanal':1.0,'quincenal':2.2,'mensual':4.33}
NCUOTAS = {'P26S':26,'P39S':39,'P52S':52,'P78S':78}

# ── Execution ─────────────────────────────────────────────────────────────────

now = datetime.now(timezone.utc).isoformat()
ins = upd = err = 0

for lb in LBS:
    try:
        n       = NCUOTAS[lb['plan']]
        mult    = MULT[lb['modo_pago']]
        valor   = math.ceil(lb['cuota_base'] * mult)
        pagadas = lb.get('cuotas_pagadas', 0)
        primera = primer_mierc(lb['fecha_entrega'])

        # Cuota inicial (numero 0) — always "pagada" on fecha_entrega
        cuota_0 = {
            'numero': 0,
            'tipo': 'inicial',
            'fecha_vencimiento': lb['fecha_factura'],
            'valor': lb['cuota_inicial'],
            'estado': 'pagada',
            'fecha_pago': lb['fecha_entrega'],
            'valor_pagado': lb['cuota_inicial'],
            'metodo_pago': 'transferencia',
            'alegra_payment_id': None,
            'comprobante': None,
            'notas': 'Carga masiva inicial',
        }

        # Regular cuotas 1..n  (with cuotas_pagadas already marked)
        cuotas_reg = cronograma(primera, n, valor, lb['modo_pago'], pagadas)
        # Normalise field names to match backend schema
        cuotas_full = [cuota_0]
        for c in cuotas_reg:
            cuotas_full.append({
                'numero':            c['numero'],
                'tipo':              lb['modo_pago'],
                'fecha_vencimiento': c['fecha'],
                'valor':             c['valor'],
                'estado':            c['estado'],
                'fecha_pago':        c['fecha_pago'],
                'valor_pagado':      c['valor'] if c['estado'] == 'pagada' else 0.0,
                'metodo_pago':       c.get('metodo_pago'),
                'alegra_payment_id': c['alegra_payment_id'],
                'comprobante':       None,
                'notas':             '',
            })

        num_pagadas_total = 1 + pagadas       # cuota_0 + regular pagadas
        total_cobrado     = lb['cuota_inicial'] + valor * pagadas
        valor_financiado  = lb['valor_total'] - lb['cuota_inicial']
        saldo_pendiente   = valor * (n - pagadas)

        existing = db.loanbook.find_one({'moto_chasis': lb['moto_chasis']})
        codigo   = existing['codigo'] if existing else sig_codigo()

        doc = {
            'codigo':              codigo,
            'cliente_nombre':      lb['cliente_nombre'],
            'cliente_nit':         lb['cliente_cedula'],
            'cliente_tipo_doc':    lb['cliente_tipo_doc'],
            'cliente_telefono':    lb.get('cliente_telefono', ''),
            'moto_chasis':         lb['moto_chasis'],
            'moto_motor':          lb['moto_motor'],
            'moto_descripcion':    f"{lb['moto_referencia']} {lb['moto_color']}",
            'moto_referencia':     lb['moto_referencia'],
            'moto_color':          lb['moto_color'],
            'moto_placa':          lb['moto_placa'],
            'plan':                lb['plan'],
            'modo_pago':           lb['modo_pago'],
            'cuota_base':          lb['cuota_base'],
            'valor_cuota':         valor,
            'cuota_valor':         valor,           # alias de compatibilidad
            'precio_venta':        lb['valor_total'],
            'cuota_inicial':       lb['cuota_inicial'],
            'valor_financiado':    valor_financiado,
            'num_cuotas':          n,
            'fecha_factura':       lb['fecha_factura'],
            'fecha_entrega':       lb['fecha_entrega'],
            'fecha_primer_pago':   primera.strftime('%Y-%m-%d'),
            'cuotas':              cuotas_full,
            'num_cuotas_pagadas':  num_pagadas_total,
            'num_cuotas_vencidas': 0,
            'total_cobrado':       total_cobrado,
            'saldo_pendiente':     saldo_pendiente,
            'estado':              'activo',
            'datos_completos':     True,
            'campos_pendientes':   [],
            'ai_suggested':        False,
            'updated_at':          now,
        }

        res = db.loanbook.update_one(
            {'moto_chasis': lb['moto_chasis']},
            {
                '$set': doc,
                '$setOnInsert': {
                    'id':         str(uuid.uuid4()),
                    'created_at': now,
                },
            },
            upsert=True,
        )

        if res.upserted_id:
            ins += 1
            print(f'  INSERTADO   {codigo} — {lb["cliente_nombre"]}  ({lb["moto_chasis"]})')
        else:
            upd += 1
            print(f'  ACTUALIZADO {codigo} — {lb["cliente_nombre"]}  ({lb["moto_chasis"]})')

    except Exception as e:
        err += 1
        print(f'  ERROR {lb["moto_chasis"]}: {e}')

print(f'\nResultado: {ins} insertados, {upd} actualizados, {err} errores — {ins+upd} total.')
client.close()
