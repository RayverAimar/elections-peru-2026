import type { TopicMeta } from './types';

export const ELECTION_DATE = new Date('2026-04-12');

export const SITE_TITLE = 'Chasqui — Tu mensajero electoral';
export const SITE_DESCRIPTION =
  'Tu mensajero electoral para las Elecciones 2026 del Perú. Quiz adaptativo, chat inteligente sobre planes de gobierno y análisis de 36 partidos políticos.';

export const ANSWER_LABELS: Record<number, string> = {
  [-2]: 'Totalmente en desacuerdo',
  [-1]: 'En desacuerdo',
  0: 'Neutral',
  1: 'De acuerdo',
  2: 'Totalmente de acuerdo',
};

export const IMPORTANCE_LABELS: Record<number, string> = {
  1: 'Normal',
  1.5: 'Importante',
  2: 'Muy importante',
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'Alta confianza',
  medium: 'Confianza media',
  low: 'Baja confianza',
};

// Dark-mode style maps — single source of truth
export const CONFIDENCE_STYLES: Record<string, string> = {
  high: 'bg-green-500/10 text-green-400',
  medium: 'bg-yellow-500/10 text-yellow-400',
  low: 'bg-red-500/10 text-red-400',
};

export const SENTIMENT_LABELS: Record<string, string> = {
  positive: 'Positivo',
  neutral: 'Neutral',
  adverse: 'Adverso',
};

export const SENTIMENT_STYLES: Record<string, string> = {
  positive: 'bg-green-500/10 text-green-400',
  neutral: 'bg-yellow-500/10 text-yellow-400',
  adverse: 'bg-red-500/10 text-red-400',
};

export const TOPICS: Record<string, TopicMeta> = {
  economics: {
    name: 'Economía',
    description: 'Política económica, empleo, impuestos, informalidad, inversión',
    axes: ['intervencion_estatal', 'gasto_social', 'formalizacion'],
  },
  education: {
    name: 'Educación',
    description: 'Inversión educativa, calidad, rol del sector privado, currículo',
    axes: ['inversion_publica', 'rol_privado'],
  },
  health: {
    name: 'Salud',
    description: 'Sistema de salud, cobertura universal, infraestructura hospitalaria',
    axes: ['sistema_universal', 'descentralizacion'],
  },
  security: {
    name: 'Seguridad Ciudadana',
    description: 'Crimen, narcotráfico, policía, penas, Fuerzas Armadas',
    axes: ['mano_dura', 'ffaa_seguridad'],
  },
  corruption: {
    name: 'Corrupción y Reforma del Estado',
    description: 'Transparencia, reforma judicial, lucha anticorrupción, reforma política',
    axes: ['reforma_judicial', 'transparencia'],
  },
  mining_environment: {
    name: 'Minería y Medio Ambiente',
    description: 'Actividad minera, regulación ambiental, comunidades, Amazonía',
    axes: ['prioridad_ambiental', 'regulacion'],
  },
  pensions: {
    name: 'Pensiones',
    description: 'AFP, ONP, sistema previsional, jubilación',
    axes: ['sistema_pensionario', 'universalidad'],
  },
  agriculture: {
    name: 'Agricultura',
    description: 'Pequeña agricultura, agroindustria, subsidios, seguridad alimentaria',
    axes: ['subsidios', 'pequeno_agricultor'],
  },
  infrastructure: {
    name: 'Infraestructura y Transporte',
    description: 'Obras públicas, APP, descentralización, transporte',
    axes: ['inversion_modelo', 'descentralizacion'],
  },
  social_rights: {
    name: 'Derechos Sociales',
    description: 'Aborto, matrimonio igualitario, enfoque de género, pueblos indígenas',
    axes: ['progresismo_social', 'igualdad_genero'],
  },
  constitution: {
    name: 'Constitución',
    description: 'Nueva constitución, asamblea constituyente, reformas constitucionales',
    axes: ['nueva_constitucion', 'reforma_politica'],
  },
  foreign_policy: {
    name: 'Política Exterior',
    description: 'Relaciones internacionales, integración regional, comercio exterior',
    axes: ['integracion_regional', 'apertura_comercial'],
  },
  technology: {
    name: 'Tecnología y Digitalización',
    description: 'Gobierno digital, conectividad, innovación, regulación tecnológica',
    axes: ['gobierno_digital', 'datos_personales'],
  },
};

export const EVENT_CATEGORIES: Record<string, { name: string; color: string }> = {
  democracy: { name: 'Democracia', color: 'text-blue-400 bg-blue-500/10' },
  corruption: { name: 'Corrupción', color: 'text-red-400 bg-red-500/10' },
  human_rights: { name: 'Derechos Humanos', color: 'text-purple-400 bg-purple-500/10' },
  economy: { name: 'Economía', color: 'text-yellow-400 bg-yellow-500/10' },
  institutional: { name: 'Institucional', color: 'text-orange-400 bg-orange-500/10' },
  justice: { name: 'Justicia', color: 'text-cyan-400 bg-cyan-500/10' },
};

export const EVENT_STANCES: Record<string, { name: string; color: string }> = {
  supported: { name: 'Apoyó', color: 'text-green-400' },
  opposed: { name: 'Se opuso', color: 'text-red-400' },
  abstained: { name: 'Se abstuvo', color: 'text-yellow-400' },
  involved: { name: 'Involucrado', color: 'text-orange-400' },
};

export const CUESTIONABLE_STANCES: Record<string, { label: string; color: string }> = {
  supported: { label: 'Votó a favor', color: 'text-red-400 bg-red-500/10' },
  involved: { label: 'Involucrado', color: 'text-orange-400 bg-orange-500/10' },
  abstained: { label: 'Se abstuvo', color: 'text-yellow-400 bg-yellow-500/10' },
};
