const CATEGORY_KEY_BY_NAME = {
  头条: 'headline',
  社会: 'society',
  国内: 'domestic',
  国际: 'international',
  娱乐: 'entertainment',
  体育: 'sports',
  军事: 'military',
  科技: 'technology',
  财经: 'finance',
  更多: 'more'
}

export function categoryLabel(name, t) {
  const key = CATEGORY_KEY_BY_NAME[name]
  return key ? t(`home.categories.${key}`) : name
}

export function isMoreCategory(name) {
  return name === '更多'
}
