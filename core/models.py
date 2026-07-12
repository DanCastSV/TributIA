from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator


class PerfilTributario(models.Model):

    TIPO_CONTRIBUYENTE = [
        ('empleado', 'Empleado'),
        ('freelance', 'Freelance'),
        ('empresa', 'Empresa'),
        ('otro', 'Otro')
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    dui = models.CharField(max_length=10, blank=True)

    nit = models.CharField(max_length=20, blank=True)

    telefono = models.CharField(max_length=15, blank=True)

    salario_mensual = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    actividad_economica = models.CharField(
        max_length=200,
        blank=True
    )

    tipo_contribuyente = models.CharField(
        max_length=20,
        choices=TIPO_CONTRIBUYENTE,
        default='empleado'
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )


class DocumentoTributario(models.Model):

    TIPOS_DOCUMENTO = [
        ('constancia_salarial', 'Constancia Salarial'),
        ('declaracion_renta', 'Declaración de Renta'),
        ('comprobante_retension', 'Comprobante de Retención'),
        ('factura', 'Factura'),
        ('otro', 'Otro'),
    ]

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('analizado', 'Analizado'),
        ('error', 'Error')
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='documentos'
    )

    nombre = models.CharField(max_length=255)

    tipo_documento = models.CharField(
        max_length=50,
        choices=TIPOS_DOCUMENTO,
        default='otro'
    )

    archivo = models.FileField(
        upload_to='documentos/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg'])]
    )

    texto_extraido = models.TextField(blank=True, null=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente'
    )

    fecha_subida = models.DateTimeField(auto_now_add=True)

    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def obtener_extension(self):
        return self.archivo.name.split('.')[-1].lower()


class AnalisisDocumento(models.Model):

    documento = models.OneToOneField(
        DocumentoTributario,
        on_delete=models.CASCADE,
        related_name='analisis'
    )

    # ==========================
    # TEXTO EXTRAÍDO
    # ==========================

    texto_extraido = models.TextField()

    # ==========================
    # IDENTIFICADORES
    # ==========================

    nit_tradicional = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    identificador_homologado = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    # ==========================
    # DATOS EXTRAÍDOS CON SPACY
    # ==========================

    nombre_empresa = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    nombre_cliente = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    fecha_documento = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    numero_documento = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    direccion_detectada = models.TextField(
        blank=True,
        null=True
    )

    # ==========================
    # CLASIFICACIÓN DEL DOCUMENTO
    # ==========================

    tipo_documento_detectado = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    categoria_detectada = models.CharField(
        max_length=50,
        blank=True,
        default='tributario'
    )

    confianza_clasificacion = models.FloatField(
        default=0.5
    )

    # ==========================
    # MONTOS DETECTADOS
    # ==========================

    montos_detectados = models.TextField(
        blank=True,
        null=True
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    otros_cargos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    # DATOS FISCALES ADICIONALES

    nrc = models.CharField(
    max_length=30,
    blank=True,
    null=True
    )

    telefono = models.CharField(
    max_length=30,
    blank=True,
    null=True
    )

    correo = models.EmailField(
    blank=True,
    null=True
    )

    giro = models.CharField(
    max_length=255,
    blank=True,
    null=True
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    # ==========================
    # IA
    # ==========================

    resumen_ia = models.TextField(
        blank=True,
        null=True
    )

    recomendacion_ia = models.TextField(
        blank=True,
        null=True
    )

    es_documento_tributario = models.BooleanField(
        null=True,
        blank=True
    )

    es_deducible = models.BooleanField(
        null=True,
        blank=True
    )

    justificacion_deducible = models.TextField(
        blank=True,
        null=True
    )

    # ==========================
    # MÉTRICAS FUTURAS
    # ==========================

    palabras_extraidas = models.IntegerField(
        default=0
    )

    entidades_detectadas = models.IntegerField(
        default=0
    )

    # ==========================
    # FECHAS
    # ==========================

    fecha_analisis = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    # ==========================
    # REPRESENTACIÓN
    # ==========================

    def __str__(self):

        return (
            f"Análisis "
            f"{self.documento.nombre}"
        )

class EventoCalendario(models.Model):
    TIPOS = [
        ('recordatorio', 'Recordatorio'),
        ('factura', 'Factura'),
        ('vencimiento', 'Vencimiento'),
    ]

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='eventos_calendario'
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPOS, default='recordatorio')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'creado_en']

    def __str__(self):
        return f"{self.titulo} ({self.fecha})"


class ConversacionAsistente(models.Model):
    """Almacena conversaciones completas con el asistente IA"""
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversaciones'
    )
    
    titulo = models.CharField(max_length=200, default="Nueva conversación")
    
    creada_en = models.DateTimeField(auto_now_add=True)
    
    actualizada_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-actualizada_en']
        
    def __str__(self):
        return f"{self.usuario.username} - {self.titulo}"


class MensajeConversacion(models.Model):
    """Almacena cada mensaje en la conversación"""
    
    ROLES = [
        ('usuario', 'Usuario'),
        ('asistente', 'Asistente'),
    ]
    
    conversacion = models.ForeignKey(
        ConversacionAsistente,
        on_delete=models.CASCADE,
        related_name='mensajes'
    )
    
    rol = models.CharField(max_length=10, choices=ROLES)
    
    contenido = models.TextField()
    
    documentos_referenciados = models.ManyToManyField(
        DocumentoTributario,
        blank=True,
        related_name='mensajes_relacionados'
    )
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['creado_en']
        
    def __str__(self):
        return f"{self.rol}: {self.contenido[:50]}..."