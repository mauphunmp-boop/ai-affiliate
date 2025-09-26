import React from 'react';

// Helper: component lazy nhưng có thể preload() sau này nếu muốn.
export default function ReactLazyPreload(factory) {
  const Component = React.lazy(factory);
  Component.preload = factory;
  return Component;
}
