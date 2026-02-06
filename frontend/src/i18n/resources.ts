export const resources = {
  en: {
    translation: {
      nav: {
        home: 'Home',
        projects: 'Projects',
        settings: 'Settings',
      },
      layout: {
        subtitle: 'Frontend SPA',
      },
      home: {
        title: 'Routing Is Active',
        description:
          'React Router is configured for SPA navigation. Use the top navigation to switch routes without page reload.',
      },
      projects: {
        title: 'Projects',
        description: 'Placeholder route for project-related screens with TanStack Query configured.',
        loading: 'Loading summary...',
        total: 'Total projects',
        recent: 'Recently updated',
      },
      settings: {
        title: 'Settings',
        description: 'Configure local preferences and client-state utilities.',
        language: 'Language',
        languageHelper: 'Switch UI language using i18n resources.',
        sessionToken: 'Session Token',
        tokenPlaceholder: 'Enter bearer token',
        saveToken: 'Save Token',
        clearToken: 'Clear Token',
      },
      notFound: {
        title: 'Page Not Found',
        description: 'The route you requested does not exist.',
        goHome: 'Go Home',
      },
      errors: {
        boundaryTitle: 'Something went wrong',
        boundaryDescription:
          'An unexpected UI error occurred. Try refreshing this view or returning home.',
        reset: 'Try Again',
      },
    },
  },
  es: {
    translation: {
      nav: {
        home: 'Inicio',
        projects: 'Proyectos',
        settings: 'Configuración',
      },
      layout: {
        subtitle: 'SPA Frontend',
      },
      home: {
        title: 'Enrutamiento Activo',
        description:
          'React Router está configurado para navegación SPA. Usa la navegación superior para cambiar de ruta sin recargar.',
      },
      projects: {
        title: 'Proyectos',
        description: 'Ruta de ejemplo para pantallas de proyectos con TanStack Query configurado.',
        loading: 'Cargando resumen...',
        total: 'Total de proyectos',
        recent: 'Actualizados recientemente',
      },
      settings: {
        title: 'Configuración',
        description: 'Configura preferencias locales y utilidades de estado del cliente.',
        language: 'Idioma',
        languageHelper: 'Cambia el idioma de la UI usando recursos i18n.',
        sessionToken: 'Token de sesión',
        tokenPlaceholder: 'Ingresa token bearer',
        saveToken: 'Guardar Token',
        clearToken: 'Limpiar Token',
      },
      notFound: {
        title: 'Página no encontrada',
        description: 'La ruta solicitada no existe.',
        goHome: 'Ir al inicio',
      },
      errors: {
        boundaryTitle: 'Algo salió mal',
        boundaryDescription:
          'Ocurrió un error inesperado en la interfaz. Intenta recargar esta vista o volver al inicio.',
        reset: 'Intentar de nuevo',
      },
    },
  },
} as const
