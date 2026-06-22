// Contenido de las guías de uso del LMS, mostradas en la página /ayuda según el
// rol del usuario. Fuente única: los manuales del vault RBS_Brain
//   70 - Resources/LMS - Manual del Estudiante.md
//   70 - Resources/LMS - Manual del Docente.md
// Al portarlos aquí se quitó el frontmatter YAML, los enlaces internos [[...]] y
// las notas de navegación entre manuales. Si se editan los manuales del vault,
// actualizar también estas constantes (mantener ambos sincronizados).

export const GUIA_ESTUDIANTE = `
# Guía del Estudiante

Una guía corta para usar la plataforma: entrar, ver tus cursos, abrir los
materiales, entregar tareas y consultar tus notas. Está pensada para hacer solo
lo que un estudiante necesita.

## 1. Entrar a la plataforma

1. Abre el enlace del LMS que te compartieron.
2. Inicia sesión con tu **correo** y tu **contraseña**.
   - Si llegas desde el portal RobotSchool, puede que entres directamente sin
     volver a escribir la contraseña (inicio de sesión unificado).
3. Si olvidaste o nunca recibiste tu contraseña, avísale a tu docente o al
   administrador: ellos pueden restablecerla.

> Tu acceso es **personal**. No compartas tu contraseña.

## 2. Ver tus cursos

- Al entrar verás **tus cursos** — los cursos en los que estás matriculado.
- Entra a un curso para ver su contenido organizado en **unidades**.
- Solo verás las unidades y materiales que tu docente haya **publicado**. Si algo
  no aparece todavía, es porque aún no está publicado.

## 3. Ver los materiales

Dentro de cada unidad encontrarás materiales de distintos tipos:

| Tipo | Qué es |
|------|--------|
| **PDF** | Documento para leer o descargar |
| **Texto** | Contenido escrito directamente en la plataforma |
| **Video** | Video de la clase o explicación |
| **Enlace** | Link a un recurso externo |

Ábrelos en el orden en que aparecen: ese es el orden que definió tu docente.

## 4. Entregar una tarea

1. Dentro de la unidad, abre la **tarea** (puede tener fecha de entrega y nota
   máxima).
2. Escribe tu respuesta y/o **adjunta tu archivo** (hasta 100 MB).
3. Envía la entrega.
4. Si tu docente lo permite, podrás ver tu entrega después de enviarla.

> Revisa la **fecha de entrega** de cada tarea. Entrega antes de que venza.

## 5. Ver tus notas y la retroalimentación

- Cuando tu docente califique tu entrega, podrás ver:
  - La **nota** que recibiste.
  - La **retroalimentación** escrita (comentarios del docente).
- Usa esa retroalimentación para mejorar en las siguientes tareas.

## 6. Materiales compartidos (repositorio)

- Además del contenido de tus cursos, puedes tener acceso a una **biblioteca de
  archivos** compartida con tu colegio.
- Ahí encontrarás documentos, presentaciones o videos que el equipo dejó
  disponibles para ti.
- Solo verás lo que se haya compartido con tu colegio o tu línea de trabajo.

## 7. Preguntas frecuentes

**No veo un curso que debería tener.**
Estás matriculado por tu docente o director. Si falta uno, avísale a tu docente.

**No veo un material o tarea.**
Probablemente aún no está publicado. Vuelve a revisar más tarde.

**Me equivoqué en una entrega.**
Habla con tu docente; según la configuración de la tarea podrás reenviar o no.

**No puedo entrar.**
Verifica tu correo y contraseña. Si sigue fallando, pide ayuda al docente o
administrador para restablecer el acceso.
`

export const GUIA_DOCENTE = `
# Guía del Docente

Guía de uso del LMS para docentes. Cubre las dos facetas de tu rol: como
**docente** que gestiona cursos y califica, y como **participante de la
capacitación docente** (donde tú eres el que aprende y obtiene certificados).

## Mapa rápido

Como docente usas tres áreas:

| Área | Tu rol | Qué haces |
|------|--------|-----------|
| **Académico** | Docente | Gestionas tus cursos, contenidos, tareas y calificas |
| **Capacitación** | Alumno | Te inscribes en programas, ves lecciones, presentas evaluaciones, obtienes certificados |
| **Repositorio** | Lector | Consultas la biblioteca de archivos compartida |

## Parte A — Tus cursos (área académica)

### A.1 Entrar y ver tus cursos

1. Inicia sesión con tu **correo** y **contraseña** (o directo desde el portal).
2. Verás **tus cursos asignados**. Entra a uno para gestionarlo.

### A.2 Estructura de un curso

Un curso se organiza así:

\`\`\`
Curso
└── Unidad (la creas y ordenas tú)
    ├── Material (PDF · Texto · Video · Enlace)
    └── Tarea (con fecha de entrega, nota máxima y rúbrica opcional)
\`\`\`

### A.3 Crear y organizar contenido

1. **Crea unidades** dentro del curso y ordénalas como quieras que las vea el
   estudiante.
2. Dentro de cada unidad, **agrega materiales**:
   - Sube un archivo (hasta 100 MB), escribe texto, pon un video o un enlace.
   - También puedes **importar un material desde el repositorio central** en vez
     de volver a subirlo.
3. **Crea tareas** con su descripción, fecha de entrega y nota máxima. Si quieres,
   asóciale una **rúbrica** de calificación.

### A.4 Publicar (clave)

> El estudiante **solo ve lo que está publicado**. Mientras preparas el material,
> déjalo sin publicar; publícalo cuando esté listo.

- Publica/despublica unidades, materiales y tareas de forma independiente.
- Si un estudiante dice que "no ve nada", lo más común es que falte publicar.

### A.5 Calificar entregas

1. Entra a la tarea y abre las **entregas** de los estudiantes.
2. Puedes **ver el archivo** que entregó cada estudiante.
3. Asigna la **nota** y escribe la **retroalimentación**.
4. El estudiante verá su nota y tus comentarios una vez calificada.

## Parte B — Tu capacitación (área de formación docente)

> Aquí cambias de sombrero: eres **alumno**. Te inscriben en programas de
> capacitación y tu objetivo es completarlos y obtener el certificado.

### B.1 Ver tus programas

- Entra a **mis programas** para ver en cuáles estás inscrito y tu **progreso**.
- Un programa se compone de **módulos**, y cada módulo de **lecciones** y
  **evaluaciones**.

### B.2 Ver lecciones

- Las lecciones pueden ser **video, PDF, texto o contenido interactivo**.
- Ábrelas en orden. La plataforma registra las lecciones que vas completando.

### B.3 Presentar evaluaciones

Hay dos tipos:

| Tipo | Cómo funciona |
|------|---------------|
| **Quiz** | Preguntas de opción múltiple. Se califica automáticamente. |
| **Práctica** | Subes un archivo; un capacitador lo revisa y te da retroalimentación. |

- Cada evaluación tiene una **nota mínima de aprobación** y un **número máximo de
  intentos**. Revísalos antes de empezar.

### B.4 Plantillas y certificados

- Algunos programas tienen **plantillas descargables** (documentos de apoyo).
- Cuando completas todo lo requerido del programa, se emite tu **certificado**.
- Tus certificados quedan en **mis certificados**, y cada uno tiene un **código
  verificable públicamente** (cualquiera puede validarlo sin iniciar sesión).

## Parte C — Repositorio de archivos

- Es la **biblioteca compartida** del equipo.
- Como docente tienes acceso de **lectura** a las carpetas y archivos compartidos
  con tu colegio o tu línea de trabajo.
- Desde el área académica puedes **importar** materiales del repositorio a tus
  unidades sin volver a subirlos.

## Preguntas frecuentes

**Un estudiante no ve un material o tarea.**
Revisa que esté **publicado**. Es la causa más frecuente.

**¿Puedo reutilizar un archivo en varias unidades?**
Sí: súbelo una vez al repositorio e **impórtalo** donde lo necesites.

**¿Quién matricula a los estudiantes en mi curso?**
El **director de grado** o el **administrador**. Si falta un estudiante, coordínalo
con ellos.

**Soy docente, ¿por qué aparezco como alumno en capacitación?**
Es correcto: en el área de **capacitación docente** tú eres el que aprende. Son
dos roles distintos dentro de la misma plataforma.

**No puedo entrar.**
Verifica correo y contraseña. Si persiste, pide al administrador que restablezca
tu acceso.
`
