import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import '@/i18n'

afterEach(() => {
  cleanup()
})

// jsdom lacks the pointer-capture and scrolling APIs that Radix Select calls.
const element = Element.prototype as unknown as Record<string, unknown>
element.scrollIntoView ??= () => {}
element.hasPointerCapture ??= () => false
element.releasePointerCapture ??= () => {}
