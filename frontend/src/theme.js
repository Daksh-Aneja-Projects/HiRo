// /frontend/src/theme.js - FINAL STABILIZATION
/** * CRITICAL FIX: Unified Theme Token Definition (Holographic / Dark Mode) 
 * Used by all components for consistent styling.
 */
const primaryColor = '#00c8ff'; // Neon Blue/Cyan
const secondaryColor = '#ff6b6b'; // Red/Danger for HRBP/Alerts
const warningColor = '#ffc300'; // Yellow/Amber for Manager/Warnings
const successColor = '#4bff83'; // Green for HRIT/Success
const bg900 = '#0a1930'; // Darker background
const panel800 = '#132c4e'; // Card background
const panel700 = '#1a375f'; // Input/Muted background
const border600 = '#324a74'; // Border color

// Helper for RGB color extraction (CRITICAL FIX: Ensure this utility is correct)
export const hexToRgb = (hex) => {
    if (!hex) return '0,0,0';
    const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
    hex = hex.replace(shorthandRegex, (m, r, g, b) => r + r + g + g + b + b);
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '0,0,0';
};

// Define core theme object
export const theme = {
    // 1. Colors
    color: {
        'accent-primary': primaryColor, // Core System/Primary Accent
        'accent-secondary': secondaryColor, // Secondary Accent (e.g., Profile, HRBP)
        'success': successColor,        // HRIT/Success Status
        'warning': warningColor,        // Manager/Warning Status
        'danger': secondaryColor,       // Critical/Error/HRBP Primary
        // RGB equivalents for opacity usage (Crucial for holographic glow effects)
        'accent-primary-rgb': hexToRgb(primaryColor), 
        'success-rgb': hexToRgb(successColor),
        'warning-rgb': hexToRgb(warningColor),
        'danger-rgb': hexToRgb(secondaryColor),
        // Backgrounds
        'bg-900': bg900,
        'bg-input': 'rgba(255,255,255,0.02)', // Very subtle white tint
        // Panels/Cards
        'panel-900': bg900,         // Darkest (Sidebar)
        'panel-800': panel800,      // Main Card Background
        'panel-700': panel700,      // Subtle Inner Background (e.g., Input, Code Block)
        'panel-600': '#254471',     // Hover states
        // Text
        'text-100': '#e0f7fa',      // Bright White/Cyan
        'muted-500': '#8f9fb2',     // Subdued Text (Subtitle/Label)
        // Borders/Dividers
        'border-600': border600,
        'border-700': '#213a60',
        'inner-divider': 'rgba(255, 255, 255, 0.08)', // New: Explicit inner divider
        'accent-2': 'rgba(0, 200, 255, 0.1)', // Subtle accent background
        'accent': '#9575cd', // General Accent (e.g., Purple)
    },
    // 2. Typography
    typography: {
        // ENHANCEMENT: Prioritize Inter, fall back to crisp system fonts
        fontFamily: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
        fontMono: "'JetBrains Mono', monospace", // Added for code boxes
        h1: { fontSize: '1.8rem', lineHeight: '1.2', fontWeight: 700 }, // Page Title
        h2: {
            fontSize: '1.2rem', lineHeight: '1.4', fontWeight: 600
        }, // Card Title/Key Value
        base: { fontSize: '1rem', lineHeight: '1.5', fontWeight: 400 }, // Body Text
        small: { fontSize: '0.85rem', lineHeight: '1.4', fontWeight: 400 }, // Subtle Text/Labels
    },
    // 3. Spacing (Modular Scale)
    spacing: {
        xxs: '4px',
        xs: '8px',
        sm: '12px',
        md: '16px',
        lg: '24px', // Standard component separation
        xl: '32px',
        chartPadding: '16px 20px 10px 10px',
        cardPadding: '20px', // Uniform card internal padding
        colGutter: '24px', // Grid column spacing (use `lg` value)
    },
    // CRITICAL FIX: Add 'size' object pointing to the correct UI widths to resolve TypeError
    size: {
        sidebarWidthExpanded: '260px', 
        sidebarWidthCollapsed: '80px', 
    },
    // 4. Border & Shadow
    border: {
        radius: {
            chip: '6px',
            button: '8px',
            card: '12px',
            full: '9999px',
        }
    },
    shadow: {
        card: '0 4px 12px rgba(0, 0, 0, 0.3)',
        // CRITICAL KPI: Not too glowy, elegant holographic hover effect
        hover: `0 0 10px 2px rgba(${hexToRgb(primaryColor)}, 0.4)`,
        sidebar: '4px 0 10px rgba(0, 0, 0, 0.4)',
        activeInset: `inset 3px 0 0 ${primaryColor}`, // For active sidebar item
    },
    // 5. UI Elements (The authoritative source for these values)
    ui: {
        sidebarWidth: {
            expanded: '260px',
            collapsed: '80px',
        },
        transition: {
            micro: 'all 180ms ease',
        }
    },
    // 6. Breakpoints
    breakpoints: {
        mobile: '600px',
        tablet: '900px',
        desktop: '1400px',
    },
};