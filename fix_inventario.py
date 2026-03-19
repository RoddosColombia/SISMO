import os
from pymongo import MongoClient

c = MongoClient(os.environ['MONGO_URL'])
db = c[os.environ['DB_NAME']]

DISP = [
    '9FL25AF32VDB95022','9FL25AF32VDB95036','9FL25AF33VDB95059','9FL25AF38VDB95025',
    '9FLT81000VDB62403','9FLT81000VDB62417','9FLT81001VDB62264','9FLT81001VDB62314',
    '9FLT81003VDB62329','9FLT81004VDB62260','9FLT81006VDB62258','9FLT81006VDB62261',
    '9FLT81008VDB62410','9FLT8100XVDB62263','9FL25AF30VDB96072','9FL25AF31VDB95190',
    '9FL25AF34VDB95376','9FL25AF35VDB95371','9FL25AF35VDB96052','9FL25AF36VDB96075',
    '9FL25AF35VDB95984'
]
ENTR = [
    '9FL25AF3XVDB95057','9FLT81003VDB62413','9FL25AF39VDB95048','9FL25AF36VDB95055',
    '9FL25AF35VDB95046','9FL25AF31VDB95058','9FLT81005VDB62414','9FL25AF3XVDB95043',
    '9FLT81003VDB62265','9FL25AF30VDB95987'
]
VEND = ['9FL25AF33VDB95997','9FL25AF30VDB96167']

d = db.inventario_motos.update_many({'vin': {'$in': DISP}}, {'$set': {'estado': 'Disponible'}})
e = db.inventario_motos.update_many({'vin': {'$in': ENTR}}, {'$set': {'estado': 'Entregada'}})
v = db.inventario_motos.update_many({'vin': {'$in': VEND}}, {'$set': {'estado': 'Vendida'}})

print('Disponibles actualizadas:', d.modified_count)
print('Entregadas actualizadas:', e.modified_count)
print('Vendidas actualizadas:', v.modified_count)
print()
print('ESTADO FINAL:')
print('  Disponibles:', db.inventario_motos.count_documents({'estado': 'Disponible'}))
print('  Entregadas: ', db.inventario_motos.count_documents({'estado': 'Entregada'}))
print('  Vendidas:   ', db.inventario_motos.count_documents({'estado': 'Vendida'}))
print('  TOTAL:      ', db.inventario_motos.count_documents({}))
c.close()
