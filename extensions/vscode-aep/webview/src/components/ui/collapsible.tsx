import React, { useState } from 'react';

interface CollapsibleProps {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
}

export function Collapsible({ children, open = false, onOpenChange }: CollapsibleProps) {
    const [isOpen, setIsOpen] = useState(open);
    
    const handleToggle = () => {
        const newOpen = !isOpen;
        setIsOpen(newOpen);
        onOpenChange?.(newOpen);
    };

    return (
        <div className="collapsible">
            {React.Children.map(children, (child) => {
                if (React.isValidElement(child) && child.type === CollapsibleTrigger) {
                    return React.cloneElement(child, { onClick: handleToggle });
                }
                if (React.isValidElement(child) && child.type === CollapsibleContent) {
                    return isOpen ? child : null;
                }
                return child;
            })}
        </div>
    );
}

interface CollapsibleTriggerProps {
    children: React.ReactNode;
    onClick?: () => void;
}

export function CollapsibleTrigger({ children, onClick }: CollapsibleTriggerProps) {
    return (
        <button onClick={onClick} className="w-full text-left">
            {children}
        </button>
    );
}

interface CollapsibleContentProps {
    children: React.ReactNode;
}

export function CollapsibleContent({ children }: CollapsibleContentProps) {
    return <div className="collapsible-content">{children}</div>;
}