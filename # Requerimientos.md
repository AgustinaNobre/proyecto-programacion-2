# Requerimientos

RQ1 — Registro e inicio de sesión: El sistema permitirá a las personas registrarse como usuarios o propietarios de canchas, iniciar sesión y cerrar sesión de forma segura, garantizando el acceso a las funcionalidades correspondientes según su rol.

RQ2 — Gestión de perfil: los usuarios podrán consultar y modificar sus datos personales, mientras que los propietarios podrán gestionar la información asociada a su perfil.

RQ3 — Búsqueda: los usuarios podrán consultar canchas filtrando por deporte y zona.

RQ4 — Detalle de cancha: los usuarios podrán consultar la información detallada de una cancha, incluyendo ubicación, deportes disponibles, instalaciones, capacidad y descripción.

RQ5 — Disponibilidad: los usuarios podrán consultar los horarios disponibles de una cancha para una fecha determinada.

RQ6 — Filtrado por disponibilidad: los usuarios podrán buscar canchas disponibles para una fecha y horario determinados.

RQ7 — Reserva: los usuarios autenticados podrán reservar una cancha disponible para una fecha y horario determinados. * a definir tema de pagos, seña, métodos de pago, etc

RQ8 — Prevención de reservas superpuestas: el sistema impedirá que se realicen reservas superpuestas para una misma cancha.

RQ9 — Consulta de reservas: los usuarios podrán consultar el detalle y estado de sus reservas.

RQ10 — Historial: los usuarios podrán consultar sus reservas activas y anteriores.

RQ11 — Cancelación: los usuarios podrán cancelar sus propias reservas de acuerdo con las condiciones que se definan para la plataforma. * a definir

RQ12 — Publicación de canchas: los propietarios autenticados podrán registrar y publicar sus canchas indicando sus características, ubicación, deportes disponibles y demás información requerida.

RQ13 — Gestión de canchas: los propietarios podrán consultar, modificar y dar de baja sus propias canchas.

RQ14 — Gestión de horarios: los propietarios podrán establecer y modificar los días y horarios en los que sus canchas estarán disponibles.

RQ15 — Bloqueo de horarios: los propietarios podrán bloquear franjas horarias de sus canchas para impedir que sean reservadas durante determinados períodos.

RQ16 — Consulta de reservas recibidas: los propietarios podrán consultar las reservas realizadas en sus canchas y su estado.

RQ17 — Acumulación de puntos: los usuarios acumularán puntos al completar reservas, de acuerdo con las condiciones establecidas por la plataforma.

RQ18 — Consulta de puntos: los usuarios podrán consultar su saldo de puntos y el historial de puntos obtenidos y utilizados.

RQ19 — Canje de beneficios: los usuarios podrán utilizar los puntos acumulados para acceder a los beneficios disponibles en la plataforma.

RQ20 — Gestión de deportes: el sistema permitirá administrar los deportes disponibles para clasificar y buscar canchas.

RQ21 — Gestión de zonas: el sistema permitirá administrar las zonas utilizadas para clasificar y filtrar las canchas.

RQ22 — Administración: los administradores podrán gestionar usuarios, propietarios y canchas de acuerdo con las políticas de la plataforma.


RNF1 — Seguridad: las contraseñas deberán almacenarse utilizando mecanismos seguros de cifrado o hash y los endpoints que requieran autenticación deberán verificar la identidad del usuario.

RNF2 — Autorización: el sistema deberá garantizar que cada usuario solo pueda acceder y modificar sus propias reservas y que cada propietario solo pueda gestionar sus propias canchas.

RNF3 — Consistencia: el sistema deberá garantizar que no existan reservas confirmadas superpuestas para una misma cancha, incluso ante solicitudes simultáneas.

RNF4 — Rendimiento: las operaciones de búsqueda de canchas y consulta de disponibilidad deberán responder dentro de un tiempo máximo acordado.

RNF5 — Disponibilidad: la API deberá mantener un nivel de disponibilidad acorde con el horario de operación definido para el servicio.

RNF6 — Mantenibilidad: el código deberá estar organizado de forma modular y contar con pruebas automatizadas que permitan verificar el correcto funcionamiento de las funcionalidades principales.

RNF7 — Escalabilidad: la arquitectura del sistema deberá permitir incorporar nuevos países, ciudades, zonas, deportes, canchas y usuarios sin requerir modificaciones significativas en la estructura de la aplicación.

RNF8 — Documentación: la API deberá contar con documentación de sus endpoints, parámetros, respuestas y códigos de error.


