import { Link as RouterLink, type LinkProps } from 'react-router-dom';
import type { ReactNode } from 'react';

type CompatLinkProps = Omit<LinkProps, 'to'> & {
  href: string;
  children?: ReactNode;
};

/** Drop-in for next/link: maps href → react-router to */
export default function Link({ href, children, ...rest }: CompatLinkProps) {
  return (
    <RouterLink to={href} {...rest}>
      {children}
    </RouterLink>
  );
}
