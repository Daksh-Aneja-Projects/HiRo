#!/bin/bash
# ===================================================================
# HiRo FINAL DEPLOYMENT SCRIPT - MOTHER OF ALL TRUTH
# One command to rule them all
# ===================================================================

set -e

echo "🚀 HiRo FINAL DEPLOYMENT"
echo "=========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check prerequisites
print_step "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed"
    exit 1
fi

# Step 1: Generate environment files
print_step "Step 1: Generating environment files..."
if [ -f "./generate_env.sh" ]; then
    chmod +x ./generate_env.sh
    ./generate_env.sh
    print_success "Environment files generated"
else
    print_warning "generate_env.sh not found, using existing .env files"
fi

# Step 2: Stop existing services
print_step "Step 2: Stopping existing services..."
docker-compose down --remove-orphans
print_success "Services stopped"

# Step 3: Reset test users
print_step "Step 3: Resetting test users..."
if [ -f "./backend/reset_test_users.py" ]; then
    cd backend && python reset_test_users.py && cd ..
    print_success "Test users reset"
else
    print_warning "reset_test_users.py not found, skipping"
fi

# Step 4: Build and start services
print_step "Step 4: Building and starting services..."
docker-compose up -d --build
print_success "Services started"

# Step 5: Wait for services to be ready
print_step "Step 5: Waiting for services to be ready..."
sleep 10

# Step 6: Health check
print_step "Step 6: Running health check..."
if [ -f "./backend/health_check.py" ]; then
    cd backend && python health_check.py && cd ..
else
    # Simple curl check
    echo "Checking backend health..."
    if curl -s http://localhost:8001/api/health | grep -q "healthy"; then
        print_success "Backend is healthy"
    else
        print_error "Backend health check failed"
    fi
    
    echo "Checking frontend..."
    if curl -s http://localhost:3000 | grep -q "HiRo"; then
        print_success "Frontend is healthy"
    else
        print_warning "Frontend might still be starting"
    fi
fi

# Step 7: Display summary
print_step "Step 7: Deployment Summary"
echo -e "\n${GREEN}✅ DEPLOYMENT COMPLETE${NC}"
echo "========================================"
echo ""
echo "📊 SERVICES:"
echo "   • Backend API: http://localhost:8001"
echo "   • Frontend UI: http://localhost:3000"
echo "   • API Docs: http://localhost:8001/api/docs"
echo ""
echo "🔑 TEST CREDENTIALS:"
echo "   1. ${YELLOW}admin/admin${NC} → Admin Portal (Full Access)"
echo "   2. ${YELLOW}manager/manager${NC} → Manager Portal (Team Management)"
echo "   3. ${YELLOW}demo/demo${NC} → Employee Portal (Self-Service)"
echo ""
echo "📁 ENVIRONMENT FILES:"
echo "   • Root: $(pwd)/.env (Single Source of Truth)"
echo "   • Backend: $(pwd)/backend/.env (Auto-generated)"
echo "   • Frontend: $(pwd)/frontend/.env (Auto-generated)"
echo ""
echo "🔧 USEFUL COMMANDS:"
echo "   • View logs: ${BLUE}docker-compose logs -f${NC}"
echo "   • Restart services: ${BLUE}docker-compose restart${NC}"
echo "   • Full reset: ${BLUE}./deploy_all.sh${NC}"
echo "   • Check status: ${BLUE}docker-compose ps${NC}"
echo ""
echo "🚀 NEXT STEPS:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Login with one of the test credentials"
echo "   3. Verify portal access matches user role"
echo ""
echo "📞 TROUBLESHOOTING:"
echo "   • Check logs: ${BLUE}docker-compose logs backend${NC}"
echo "   • Reset users: ${BLUE}cd backend && python reset_test_users.py${NC}"
echo "   • Rebuild: ${BLUE}docker-compose up -d --build${NC}"

# Step 8: Open browser (optional)
read -p "Open browser to HiRo? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:3000"
    elif command -v open &> /dev/null; then
        open "http://localhost:3000"
    else
        echo "Please open http://localhost:3000 in your browser"
    fi
fi

echo -e "\n${GREEN}🎉 HiRo IS READY!${NC}"