"""Mock data for demo mode — NIIF Colombia Plan de Cuentas + Sample Data"""

MOCK_COMPANY = {
    "id": "demo-company",
    "name": "Empresa Demo RODDOS S.A.S.",
    "nit": "900.123.456-7",
    "address": "Carrera 7 No. 71-21 Piso 4, Bogotá D.C.",
    "phone": "+57 1 3456789",
    "email": "info@roddos.com.co",
    "regime": "simplificado",
    "currency": "COP",
}

MOCK_ACCOUNTS = [
    {
        "id": "1", "code": "1", "name": "ACTIVOS", "type": "asset", "status": "active",
        "subAccounts": [
            {
                "id": "11", "code": "11", "name": "EFECTIVO Y EQUIVALENTES AL EFECTIVO", "type": "asset", "status": "active",
                "subAccounts": [
                    {"id": "1105", "code": "1105", "name": "Caja", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1110", "code": "1110", "name": "Bancos", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1115", "code": "1115", "name": "Cuentas de ahorro", "type": "asset", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "13", "code": "13", "name": "DEUDORES COMERCIALES Y CUENTAS POR COBRAR", "type": "asset", "status": "active",
                "subAccounts": [
                    {"id": "1305", "code": "1305", "name": "Clientes nacionales", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1310", "code": "1310", "name": "Clientes del exterior", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1355", "code": "1355", "name": "Anticipo de impuestos y retenciones", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1360", "code": "1360", "name": "Reclamaciones", "type": "asset", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "14", "code": "14", "name": "INVENTARIOS", "type": "asset", "status": "active",
                "subAccounts": [
                    {"id": "1405", "code": "1405", "name": "Materias primas", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1430", "code": "1430", "name": "Mercancías no fabricadas", "type": "asset", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "15", "code": "15", "name": "PROPIEDADES, PLANTA Y EQUIPO", "type": "asset", "status": "active",
                "subAccounts": [
                    {"id": "1504", "code": "1504", "name": "Terrenos", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1516", "code": "1516", "name": "Construcciones y edificaciones", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1524", "code": "1524", "name": "Maquinaria y equipo", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1528", "code": "1528", "name": "Equipo de oficina", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1536", "code": "1536", "name": "Equipo de computación y comunicación", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "1592", "code": "1592", "name": "Depreciación acumulada (CR)", "type": "asset", "status": "active", "subAccounts": []},
                ]
            },
        ]
    },
    {
        "id": "2", "code": "2", "name": "PASIVOS", "type": "liability", "status": "active",
        "subAccounts": [
            {
                "id": "22", "code": "22", "name": "PROVEEDORES", "type": "liability", "status": "active",
                "subAccounts": [
                    {"id": "2205", "code": "2205", "name": "Proveedores nacionales", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2210", "code": "2210", "name": "Proveedores del exterior", "type": "liability", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "23", "code": "23", "name": "CUENTAS POR PAGAR", "type": "liability", "status": "active",
                "subAccounts": [
                    {"id": "2335", "code": "2335", "name": "Costos y gastos por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2365", "code": "2365", "name": "Retención en la fuente por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2367", "code": "2367", "name": "ReteIVA por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2368", "code": "2368", "name": "ReteICA por pagar", "type": "liability", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "24", "code": "24", "name": "IMPUESTOS, GRAVÁMENES Y TASAS", "type": "liability", "status": "active",
                "subAccounts": [
                    {"id": "2404", "code": "2404", "name": "Impuesto de renta por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2408", "code": "2408", "name": "IVA por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2409", "code": "2409", "name": "IVA descontable", "type": "asset", "status": "active", "subAccounts": []},
                    {"id": "2460", "code": "2460", "name": "ICA por pagar", "type": "liability", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "25", "code": "25", "name": "OBLIGACIONES LABORALES", "type": "liability", "status": "active",
                "subAccounts": [
                    {"id": "2505", "code": "2505", "name": "Nómina por pagar", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2510", "code": "2510", "name": "Cesantías consolidadas", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2515", "code": "2515", "name": "Intereses sobre cesantías", "type": "liability", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "26", "code": "26", "name": "PROVISIONES", "type": "liability", "status": "active",
                "subAccounts": [
                    {"id": "2610", "code": "2610", "name": "Provisión cesantías", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2615", "code": "2615", "name": "Provisión intereses cesantías", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2620", "code": "2620", "name": "Provisión prima de servicios", "type": "liability", "status": "active", "subAccounts": []},
                    {"id": "2625", "code": "2625", "name": "Provisión vacaciones", "type": "liability", "status": "active", "subAccounts": []},
                ]
            },
        ]
    },
    {
        "id": "3", "code": "3", "name": "PATRIMONIO", "type": "equity", "status": "active",
        "subAccounts": [
            {"id": "3105", "code": "3105", "name": "Capital suscrito y pagado", "type": "equity", "status": "active", "subAccounts": []},
            {"id": "3205", "code": "3205", "name": "Prima en colocación de acciones", "type": "equity", "status": "active", "subAccounts": []},
            {"id": "3305", "code": "3305", "name": "Reserva legal", "type": "equity", "status": "active", "subAccounts": []},
            {"id": "3605", "code": "3605", "name": "Utilidades del ejercicio", "type": "equity", "status": "active", "subAccounts": []},
            {"id": "3610", "code": "3610", "name": "Pérdida del ejercicio", "type": "equity", "status": "active", "subAccounts": []},
        ]
    },
    {
        "id": "4", "code": "4", "name": "INGRESOS", "type": "income", "status": "active",
        "subAccounts": [
            {
                "id": "41", "code": "41", "name": "INGRESOS OPERACIONALES", "type": "income", "status": "active",
                "subAccounts": [
                    {"id": "4105", "code": "4105", "name": "Ingresos por ventas de productos", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4135", "code": "4135", "name": "Ingresos por servicios", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4155", "code": "4155", "name": "Ingresos por honorarios", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4175", "code": "4175", "name": "Ingresos por comisiones", "type": "income", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "42", "code": "42", "name": "INGRESOS NO OPERACIONALES", "type": "income", "status": "active",
                "subAccounts": [
                    {"id": "4210", "code": "4210", "name": "Ingresos por arrendamientos", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4225", "code": "4225", "name": "Ingresos por comisiones no operacionales", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4250", "code": "4250", "name": "Ingresos financieros", "type": "income", "status": "active", "subAccounts": []},
                    {"id": "4295", "code": "4295", "name": "Recuperaciones", "type": "income", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "44", "code": "44", "name": "SUBSIDIOS", "type": "income", "status": "active",
                "subAccounts": [
                    {"id": "4420", "code": "4420", "name": "Subsidios gubernamentales", "type": "income", "status": "active", "subAccounts": []},
                ]
            },
            {
                "id": "48", "code": "48", "name": "INGRESOS EXTRAORDINARIOS", "type": "income", "status": "active",
                "subAccounts": [
                    {"id": "4800", "code": "4800", "name": "Ingresos extraordinarios", "type": "income", "status": "active", "subAccounts": []},
                ]
            },
        ]
    },
    {
        "id": "5", "code": "5", "name": "GASTOS DE ADMINISTRACIÓN", "type": "expense", "status": "active",
        "subAccounts": [
            {"id": "5105", "code": "5105", "name": "Gastos de personal - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5110", "code": "5110", "name": "Honorarios - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5115", "code": "5115", "name": "Impuestos - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5120", "code": "5120", "name": "Arrendamientos - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5125", "code": "5125", "name": "Contribuciones y afiliaciones", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5130", "code": "5130", "name": "Seguros - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5135", "code": "5135", "name": "Servicios - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5145", "code": "5145", "name": "Mantenimiento y reparaciones", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5160", "code": "5160", "name": "Depreciaciones - administración", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5185", "code": "5185", "name": "Servicios públicos", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5195", "code": "5195", "name": "Gastos generales - administración", "type": "expense", "status": "active", "subAccounts": []},
        ]
    },
    {
        "id": "52", "code": "52", "name": "GASTOS DE VENTAS", "type": "expense", "status": "active",
        "subAccounts": [
            {"id": "5205", "code": "5205", "name": "Gastos de personal - ventas", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5260", "code": "5260", "name": "Publicidad y propaganda", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5295", "code": "5295", "name": "Gastos generales - ventas", "type": "expense", "status": "active", "subAccounts": []},
        ]
    },
    {
        "id": "53", "code": "53", "name": "GASTOS NO OPERACIONALES", "type": "expense", "status": "active",
        "subAccounts": [
            {"id": "5305", "code": "5305", "name": "Gastos financieros", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5310", "code": "5310", "name": "Pérdida en venta y retiro de bienes", "type": "expense", "status": "active", "subAccounts": []},
        ]
    },
    {
        "id": "54", "code": "54", "name": "IMPUESTOS, GRAVÁMENES Y TASAS", "type": "expense", "status": "active",
        "subAccounts": [
            {"id": "5405", "code": "5405", "name": "Impuesto de renta y complementarios", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5415", "code": "5415", "name": "Impuesto de industria y comercio (ICA)", "type": "expense", "status": "active", "subAccounts": []},
            {"id": "5420", "code": "5420", "name": "Predial y complementarios", "type": "expense", "status": "active", "subAccounts": []},
        ]
    },
    {
        "id": "6", "code": "6", "name": "COSTOS DE VENTAS Y SERVICIOS", "type": "cost", "status": "active",
        "subAccounts": [
            {
                "id": "61", "code": "61", "name": "COSTOS DE VENTAS", "type": "cost", "status": "active",
                "subAccounts": [
                    {"id": "6135", "code": "6135", "name": "Costos de ventas de productos", "type": "cost", "status": "active", "subAccounts": []},
                    {"id": "6145", "code": "6145", "name": "Materiales y suministros usados", "type": "cost", "status": "active", "subAccounts": []},
                    {"id": "6155", "code": "6155", "name": "Mano de obra directa", "type": "cost", "status": "active", "subAccounts": []},
                    {"id": "6165", "code": "6165", "name": "Costos de servicios prestados", "type": "cost", "status": "active", "subAccounts": []},
                ]
            }
        ]
    },
]

MOCK_CONTACTS = [
    {"id": "c1", "name": "Constructora Colpatria S.A.", "identification": "860.007.660-1", "type": "client", "email": "pagos@colpatria.com", "phone": "3001234567"},
    {"id": "c2", "name": "Grupo Éxito S.A.", "identification": "860.007.159-8", "type": "client", "email": "proveedores@exito.com", "phone": "3009876543"},
    {"id": "c3", "name": "TeleComunicaciones SAS", "identification": "900.456.789-2", "type": "client", "email": "contabilidad@telecom.co", "phone": "3201234567"},
    {"id": "c4", "name": "Inversiones Bogotá Ltda.", "identification": "900.321.654-5", "type": "client", "email": "info@invbogota.com", "phone": "3109876543"},
    {"id": "c5", "name": "Bancolombia S.A.", "identification": "890.903.938-8", "type": "client", "email": "empresas@bancolombia.com", "phone": "018000932"},
    {"id": "p1", "name": "Arrendamientos Premium S.A.S.", "identification": "900.111.222-3", "type": "provider", "email": "arrendamientos@premium.co", "phone": "3001111222"},
    {"id": "p2", "name": "Servicios Públicos ESP", "identification": "900.222.333-4", "type": "provider", "email": "pagos@spublicos.com", "phone": "3002222333"},
    {"id": "p3", "name": "Papelería y Oficina SAS", "identification": "900.333.444-5", "type": "provider", "email": "ventas@papeleria.co", "phone": "3003333444"},
    {"id": "p4", "name": "Tecnología Empresarial Ltda.", "identification": "900.444.555-6", "type": "provider", "email": "soporte@tecnemp.co", "phone": "3004444555"},
    {"id": "p5", "name": "Asesorías Jurídicas SAS", "identification": "900.555.666-7", "type": "provider", "email": "abogados@asesoriasj.co", "phone": "3005555666"},
]

MOCK_ITEMS = [
    {"id": "i1", "name": "Consultoría Contable", "description": "Servicio mensual de consultoría contable y financiera", "price": 5000000, "tax": [{"id": "tax1", "percentage": 19}]},
    {"id": "i2", "name": "Auditoría Financiera", "description": "Auditoría de estados financieros trimestral", "price": 8500000, "tax": [{"id": "tax1", "percentage": 19}]},
    {"id": "i3", "name": "Declaración de Renta", "description": "Preparación y presentación declaración de renta", "price": 3500000, "tax": []},
    {"id": "i4", "name": "Licencia Software Contable", "description": "Licencia anual plataforma contable", "price": 2400000, "tax": [{"id": "tax1", "percentage": 19}]},
    {"id": "i5", "name": "Capacitación NIIF", "description": "Taller de actualización NIIF para PYMES - 8 horas", "price": 1500000, "tax": []},
]

MOCK_TAXES = [
    {"id": "tax1", "name": "IVA 19%", "percentage": 19, "type": "IVA"},
    {"id": "tax2", "name": "IVA 5%", "percentage": 5, "type": "IVA"},
    {"id": "tax3", "name": "IVA 0%", "percentage": 0, "type": "IVA"},
]

MOCK_RETENTIONS = [
    {"id": "ret1", "name": "ReteFuente Servicios 4%", "percentage": 4, "type": "RFTE"},
    {"id": "ret2", "name": "ReteFuente Honorarios 10%", "percentage": 10, "type": "RFTE"},
    {"id": "ret3", "name": "ReteFuente Arrendamiento 3.5%", "percentage": 3.5, "type": "RFTE"},
    {"id": "ret4", "name": "ReteIVA 15%", "percentage": 15, "type": "RIVA"},
    {"id": "ret5", "name": "ReteICA Bogotá Servicios 0.966%", "percentage": 0.966, "type": "ICA"},
]

MOCK_COST_CENTERS = [
    {"id": "cc1", "name": "Administrativo", "code": "ADM"},
    {"id": "cc2", "name": "Ventas", "code": "VTA"},
    {"id": "cc3", "name": "Operativo", "code": "OPE"},
]

MOCK_BANK_ACCOUNTS = [
    {"id": "ba1", "name": "Bancolombia - Cuenta Corriente", "number": "****6789", "bank": "Bancolombia", "balance": 45600000, "type": "checking", "account": {"id": "1110", "code": "1110", "name": "Bancos"}},
    {"id": "ba2", "name": "Davivienda - Cuenta de Ahorros", "number": "****4321", "bank": "Davivienda", "balance": 12300000, "type": "savings", "account": {"id": "1115", "code": "1115", "name": "Cuentas de ahorro"}},
]

MOCK_INVOICES = [
    {"id": "inv1", "number": "FV-2025-001", "date": "2025-10-01", "dueDate": "2025-10-31", "client": {"id": "c1", "name": "Constructora Colpatria S.A."}, "total": 5950000, "subtotal": 5000000, "taxes": 950000, "status": "open", "observations": "Consultoría contable octubre"},
    {"id": "inv2", "number": "FV-2025-002", "date": "2025-10-05", "dueDate": "2025-11-04", "client": {"id": "c2", "name": "Grupo Éxito S.A."}, "total": 10115000, "subtotal": 8500000, "taxes": 1615000, "status": "paid", "observations": "Auditoría tercer trimestre"},
    {"id": "inv3", "number": "FV-2025-003", "date": "2025-10-10", "dueDate": "2025-11-09", "client": {"id": "c3", "name": "TeleComunicaciones SAS"}, "total": 3500000, "subtotal": 3500000, "taxes": 0, "status": "open", "observations": "Declaración de renta 2024"},
    {"id": "inv4", "number": "FV-2025-004", "date": "2025-10-15", "dueDate": "2025-11-14", "client": {"id": "c4", "name": "Inversiones Bogotá Ltda."}, "total": 2856000, "subtotal": 2400000, "taxes": 456000, "status": "overdue", "observations": "Licencia software anual"},
    {"id": "inv5", "number": "FV-2025-005", "date": "2025-10-20", "dueDate": "2025-11-19", "client": {"id": "c5", "name": "Bancolombia S.A."}, "total": 1500000, "subtotal": 1500000, "taxes": 0, "status": "open", "observations": "Capacitación NIIF - Nov 2025"},
]

MOCK_BILLS = [
    {"id": "bill1", "number": "FC-2025-001", "date": "2025-10-01", "dueDate": "2025-10-31", "provider": {"id": "p1", "name": "Arrendamientos Premium S.A.S."}, "total": 3000000, "subtotal": 3000000, "taxes": 0, "status": "open", "description": "Canon arrendamiento octubre"},
    {"id": "bill2", "number": "FC-2025-002", "date": "2025-10-05", "dueDate": "2025-10-20", "provider": {"id": "p2", "name": "Servicios Públicos ESP"}, "total": 450000, "subtotal": 378151, "taxes": 71849, "status": "paid", "description": "Servicios públicos octubre"},
    {"id": "bill3", "number": "FC-2025-003", "date": "2025-10-10", "dueDate": "2025-11-09", "provider": {"id": "p3", "name": "Papelería y Oficina SAS"}, "total": 238000, "subtotal": 200000, "taxes": 38000, "status": "open", "description": "Útiles y papelería"},
    {"id": "bill4", "number": "FC-2025-004", "date": "2025-10-12", "dueDate": "2025-11-11", "provider": {"id": "p4", "name": "Tecnología Empresarial Ltda."}, "total": 1190000, "subtotal": 1000000, "taxes": 190000, "status": "open", "description": "Mantenimiento equipos"},
    {"id": "bill5", "number": "FC-2025-005", "date": "2025-10-15", "dueDate": "2025-11-14", "provider": {"id": "p5", "name": "Asesorías Jurídicas SAS"}, "total": 2380000, "subtotal": 2000000, "taxes": 380000, "status": "overdue", "description": "Honorarios asesoría legal"},
]

MOCK_JOURNAL_ENTRIES = [
    {
        "id": "je1", "number": "CE-2025-001", "date": "2025-10-01", "observations": "Causación nómina octubre 2025",
        "entries": [
            {"account": {"id": "5105", "code": "5105", "name": "Gastos de personal - administración"}, "debit": 5000000, "credit": 0},
            {"account": {"id": "2505", "code": "2505", "name": "Nómina por pagar"}, "debit": 0, "credit": 5000000},
        ]
    },
    {
        "id": "je2", "number": "CE-2025-002", "date": "2025-10-10", "observations": "Depreciación equipos octubre",
        "entries": [
            {"account": {"id": "5160", "code": "5160", "name": "Depreciaciones - administración"}, "debit": 350000, "credit": 0},
            {"account": {"id": "1592", "code": "1592", "name": "Depreciación acumulada"}, "debit": 0, "credit": 350000},
        ]
    },
]

MOCK_RECONCILIATION_ITEMS = [
    {"id": "rec1", "date": "2025-10-01", "description": "Pago nómina", "amount": -5000000, "type": "debit", "reconciled": True},
    {"id": "rec2", "date": "2025-10-05", "description": "Pago factura FV-2025-002", "amount": 10115000, "type": "credit", "reconciled": True},
    {"id": "rec3", "date": "2025-10-10", "description": "Pago arrendamiento", "amount": -3000000, "type": "debit", "reconciled": False},
    {"id": "rec4", "date": "2025-10-15", "description": "Pago factura FV-2025-001", "amount": 5950000, "type": "credit", "reconciled": False},
    {"id": "rec5", "date": "2025-10-20", "description": "Servicios públicos", "amount": -450000, "type": "debit", "reconciled": False},
]
