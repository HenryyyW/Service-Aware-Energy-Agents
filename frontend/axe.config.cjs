module.exports = {
  ci: {
    rules: {
      'color-contrast': { enabled: true },
      'keyboard': { enabled: true },
      'aria-roles': { enabled: true },
      'aria-attributes': { enabled: true },
      'focus-order-semantics': { enabled: true },
      'landmark-one-main': { enabled: true },
      'region': { enabled: true },
      'page-has-heading-one': { enabled: true },
      'heading-order': { enabled: true },
      'label': { enabled: true },
      'button-name': { enabled: true },
      'link-name': { enabled: true },
      'image-alt': { enabled: true },
      'document-title': { enabled: true },
      'html-has-lang': { enabled: true },
      'html-lang-valid': { enabled: true },
      'meta-viewport': { enabled: true },
      'skip-link': { enabled: true },
      'focus-visible': { enabled: true }
    },
    urls: [
      'http://localhost:4173/',
      'http://localhost:4173/scenario-studio',
      'http://localhost:4173/report',
      'http://localhost:4173/comparison'
    ],
    rules: {
      'color-contrast': { enabled: true, options: { minRatio: 4.5 } },
      'link-name': { enabled: true },
      'button-name': { enabled: true },
      'image-alt': { enabled: true },
      'form-field': { enabled: true },
      'label': { enabled: true },
      'document-title': { enabled: true }
    },
    threshold: 0,
    reporter: 'cli',
    saveOutput: true,
    outputDir: './axe-results'
  }
};