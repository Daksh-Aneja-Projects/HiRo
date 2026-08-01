// Plain-English rendering of approval-queue items, shared by the Manager
// portal approvals module and the HRIT organisation-wide queue.
import { fmtDate, humanText } from '../employee/shared';

export const requestKind = (type) => ({
    LEAVE_REQUEST: 'Time off',
    LEAVE: 'Time off',
    TIMESHEET: 'Timesheet',
    EXPENSE: 'Expense claim',
}[String(type || '').toUpperCase()] || humanText(type) || 'Request');

export const money = (amount, currency) => {
    const value = Number(amount);
    if (!Number.isFinite(value)) return null;
    try {
        return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency || 'USD' }).format(value);
    } catch {
        return `${currency || 'USD'} ${value.toFixed(2)}`;
    }
};

// The queue carries three different kinds of request, so each one gets a sentence
// that is actually true of it. A timesheet reported as "asked for 41 hours off"
// is the sort of thing a manager approves by mistake.
export const describeRequest = (item, who) => {
    const name = who || 'A team member';
    const hours = Number(item.hours) || 0;
    switch (String(item.type || '').toUpperCase()) {
        case 'TIMESHEET':
            return `${name} submitted a timesheet for ${hours} hours${
                item.week_ending ? `, week ending ${fmtDate(item.week_ending)}` : ''}.`;
        case 'EXPENSE': {
            const value = money(item.amount, item.currency);
            return `${name} claimed ${value || 'an expense'}${
                item.category ? ` for ${humanText(item.category).toLowerCase()}` : ''}${
                item.description ? `: ${item.description}` : ''}.`;
        }
        case 'LEAVE_REQUEST':
        case 'LEAVE':
            return `${name} has asked for ${hours} hours off${
                item.start_date ? `, from ${fmtDate(item.start_date)} to ${fmtDate(item.end_date)}` : ''}.`;
        default:
            return `${name} has raised a request.`;
    }
};
