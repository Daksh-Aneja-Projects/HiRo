// /frontend/src/pages/index.js - FINAL PRODUCTION-READY BARREL FILE (Stabilized Imports)
// Centralized barrel file to export all page components.

// --- Imports (Using default or named imports based on file structure) ---

// Assuming Default Exports (Login, UserPage, etc.)
import LoginComponent from './Login';
import AdminPortalComponent from './AdminPortal';
import HRITPortalComponent from './HRITPortal';
import HRPortalComponent from './HRPortal';
import ManagerPortalComponent from './ManagerPortal';
import EmployeePortalComponent from './EmployeePortal';
import AdvancedAnalyticsComponent from './AdvancedAnalytics';
import UltimateOrchestratorPanelComponent from './UltimateOrchestratorPanel';
import UserPageComponent from './UserPage'; 

// CRITICAL FIX: Dashboard and SocialFeed use NAMED EXPORTS from their source files.
import { Dashboard as DashboardComponent } from './Dashboard'; 
import { SocialFeed as SocialFeedComponent } from './SocialFeed'; 

// Components with potential nested paths (assuming these are shared components, not pages)
import ConfigurationAgentPanelComponent from '../components/ConfigurationAgentPanel'; 
import PolicyVerifiedChatComponent from '../components/PolicyVerifiedChat';
import RiskOverviewComponent from '../components/RiskOverview';
import TalentExperienceHubComponent from '../components/TalentExperienceHub';

// Assuming PolicyGovernanceDashboard is a page component (based on its original path)
import PolicyGovernanceDashboardComponent from './PolicyGovernanceDashboard';


// --- Export all components as named exports for easy consumption (e.g., in App.js) ---

export const Login = LoginComponent;
export const Dashboard = DashboardComponent;
export const UserPage = UserPageComponent; 
export const AdminPortal = AdminPortalComponent;
export const HRITPortal = HRITPortalComponent;
export const HRPortal = HRPortalComponent;
export const ManagerPortal = ManagerPortalComponent;
export const EmployeePortal = EmployeePortalComponent;
export const AdvancedAnalytics = AdvancedAnalyticsComponent;
export const SocialFeed = SocialFeedComponent;
export const UltimateOrchestratorPanel = UltimateOrchestratorPanelComponent;

// Exporting components that might be useful globally:
export const ConfigurationAgentPanel = ConfigurationAgentPanelComponent;
export const PolicyGovernanceDashboard = PolicyGovernanceDashboardComponent;
export const PolicyVerifiedChat = PolicyVerifiedChatComponent;
export const RiskOverview = RiskOverviewComponent;
export const TalentExperienceHub = TalentExperienceHubComponent;