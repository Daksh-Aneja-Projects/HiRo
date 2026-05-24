// src/AppWrapper.js (The new file to provide context and conditional rendering)
import React from 'react';
import { CustomizationProvider, useCustomization } from './contexts/CustomizationContext';
import { AI_UI_Commander } from './components/AI_UI_Commander';
import { DynamicDashboard } from './pages/DynamicDashboard';

// --- MOCK OF YOUR EXISTING PORTAL LAYOUT ---
const DefaultPortalLayout = () => {
    const { activeThemeHSL } = useCustomization();
    return (
        <div className="p-10 text-white">
            <h1 className="text-2xl font-bold mb-4" style={{ color: `hsl(${activeThemeHSL.hue}, 80%, 60%)` }}>
                Universal Portal: {useCustomization().userContext.userRole.toUpperCase()} View
            </h1>
            <p className="text-gray-400">
                This is the user's default, customizable dashboard (Employee, Manager, etc.).
            </p>
            <p className="text-gray-400 mt-2">
                Use the AI Commander in the bottom right to synthesize a new report or change the theme.
            </p>
            {/* PLACEHOLDER for your existing layout components (e.g., ESSDashboard, ManagerView) */}
        </div>
    );
};
// --- END MOCK ---


const MainApplicationContent = () => {
    const { synthesizedDashboardConfig } = useCustomization();
    
    return (
        <div className="min-h-screen bg-gray-900 transition-colors duration-500">
            {/* Conditional Rendering: Synthesis Report (ID 4) vs. Default Layout (ID 1) */}
            {synthesizedDashboardConfig ? (
                <DynamicDashboard />
            ) : (
                <DefaultPortalLayout />
            )}
            
            {/* The Commander always floats on top (ID 5) */}
            <AI_UI_Commander />
        </div>
    );
};

const AppWrapper = () => (
    <CustomizationProvider>
        <MainApplicationContent />
    </CustomizationProvider>
);

export default AppWrapper;

/* INSTRUCTIONS FOR INTEGRATION:
1. In your project's main entry file (e.g., src/index.js), replace the rendering of your current App component with <AppWrapper />.
2. Ensure your global CSS defines the necessary Tailwind classes and uses the CSS variables:
   :root { 
     --holo-primary-color: hsl(var(--user-hue), 80%, 60%); 
     --bg-main: hsl(var(--user-hue), 10%, 10%); 
     /* ... other variables must derive from --user-hue ... 
   }
*/