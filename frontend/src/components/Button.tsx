import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cx } from '../lib/cx';
import styles from './Button.module.css';

export type ButtonVariant = 'primary' | 'save' | 'cancel' | 'secondary';

type CommonProps = {
  variant?: ButtonVariant;
  block?: boolean;
  className?: string;
  children: ReactNode;
};

type ButtonProps = CommonProps & ButtonHTMLAttributes<HTMLButtonElement> & { to?: undefined };
type LinkProps = CommonProps & { to: string };

export function Button(props: ButtonProps | LinkProps) {
  const { variant = 'primary', block, className, children } = props;
  const classes = cx(styles.button, styles[variant], block && styles.block, className);

  if (props.to !== undefined) {
    return (
      <Link to={props.to} className={classes}>
        {children}
      </Link>
    );
  }

  const { variant: _v, block: _b, className: _c, children: _ch, type = 'button', ...rest } = props;
  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}
