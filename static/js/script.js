
const API_BASE = '/api/expenses';
const AUTH_URL = '/auth/login';

let grid = null;
let token = localStorage.getItem('access_token');
let username = localStorage.getItem('username');

// DOM Elements
const loginSection = document.getElementById('login-section');
const dashboardSection = document.getElementById('dashboard-section');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');
const userDisplay = document.getElementById('user-display');
const expenseModal = new bootstrap.Modal(document.getElementById('expenseModal'));
const saveBtn = document.getElementById('save-expense-btn');
const searchBtn = document.getElementById('search-btn');
const resetBtn = document.getElementById('reset-btn');

// --- AUTHENTICATION ---

function updateUI() {
    if (token) {
        loginSection.classList.add('d-none');
        dashboardSection.classList.remove('d-none');
        userDisplay.textContent = `Welcome, ${username || 'User'}`;
        initGrid();
    } else {
        loginSection.classList.remove('d-none');
        dashboardSection.classList.add('d-none');
    }
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const user = document.getElementById('username').value;
    const pass = document.getElementById('password').value;

    try {
        const res = await fetch(AUTH_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password: pass })
        });

        const data = await res.json();

        if (res.ok) {
            token = data.access_token;
            username = user;
            localStorage.setItem('access_token', token);
            localStorage.setItem('username', username);
            loginError.classList.add('d-none');
            updateUI();
        } else {
            throw new Error(data.error.message || 'Login failed');
        }
    } catch (err) {
        loginError.textContent = err.message;
        loginError.classList.remove('d-none');
    }
});

logoutBtn.addEventListener('click', () => {
    token = null;
    username = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    if (grid) {
        grid.destroy();
        grid = null;
        document.getElementById("grid-wrapper").innerHTML = '';
    }
    updateUI();
});

// --- GRID & DATA ---

function getAuthHeaders() {
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

function initGrid() {
    if (grid) {
        grid.forceRender();
        return;
    }

    grid = new gridjs.Grid({
        columns: [
            { id: 'expense_id', name: 'ID', hidden: true },
            { 
                id: 'expense_date', 
                name: 'Date', 
                width: '120px',
                formatter: (cell) => new Date(cell).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
            },
            { id: 'category_name', name: 'Category' },
            { id: 'vendor_name', name: 'Vendor' },
            { id: 'payment_method_name', name: 'Payment' },
            { 
                id: 'description', 
                name: 'Description', 
                width: '200px',
                formatter: (cell) => gridjs.html(`<span title="${cell}" class="text-truncate d-inline-block" style="max-width: 180px;">${cell || '-'}</span>`)
            },
            { 
                id: 'amount', 
                name: 'Amount',
                width: '120px',
                formatter: (cell) => gridjs.html(`<div class="text-end fw-bold">₱${parseFloat(cell).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>`)
            },
            {
                name: 'Actions',
                width: '100px',
                formatter: (cell, row) => {
                    return gridjs.html(`
                        <div class="d-flex justify-content-center">
                            <button class="btn btn-sm btn-outline-primary me-1" onclick="editExpense(${row.cells[0].data})" title="Edit">
                                <i class="fa-solid fa-pen"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteExpense(${row.cells[0].data})" title="Delete">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </div>
                    `);
                }
            }
        ],
        server: {
            url: API_BASE,
            headers: getAuthHeaders(),
            then: data => data.data.map(item => [
                item.expense_id,
                item.expense_date,
                item.category_name,
                item.vendor_name,
                item.payment_method_name,
                item.description,
                item.amount
            ]),
            total: data => data.count
        },
        search: false, // We implement custom search
        sort: true,
        pagination: {
            limit: 10
        },
        style: {
            table: {
                'white-space': 'nowrap'
            }
        }
    }).render(document.getElementById("grid-wrapper"));
}

// --- CRUD OPERATIONS ---

// Search
searchBtn.addEventListener('click', () => {
    const q = document.getElementById('search-q').value;
    const cat = document.getElementById('search-category').value;
    const ven = document.getElementById('search-vendor').value;
    const start = document.getElementById('search-start-date').value;
    const end = document.getElementById('search-end-date').value;

    const params = new URLSearchParams();
    if (q) params.append('q', q);
    if (cat) params.append('category', cat);
    if (ven) params.append('vendor', ven);
    if (start) params.append('start_date', start);
    if (end) params.append('end_date', end);

    const url = params.toString() ? `${API_BASE}/search?${params.toString()}` : API_BASE;
    
    grid.updateConfig({
        server: {
            url: url,
            headers: getAuthHeaders(),
            then: data => data.data.map(item => [
                item.expense_id,
                item.expense_date,
                item.category_name,
                item.vendor_name,
                item.payment_method_name,
                item.description,
                item.amount
            ])
        }
    }).forceRender();
});

resetBtn.addEventListener('click', () => {
    document.querySelectorAll('#dashboard-section input').forEach(i => i.value = '');
    grid.updateConfig({
        server: {
            url: API_BASE,
            headers: getAuthHeaders(),
            then: data => data.data.map(item => [
                item.expense_id,
                item.expense_date,
                item.category_name,
                item.vendor_name,
                item.payment_method_name,
                item.description,
                item.amount
            ])
        }
    }).forceRender();
});

// Add/Edit
const expenseForm = document.getElementById('expense-form');
const modalTitle = document.getElementById('modalTitle');

document.getElementById('add-btn').addEventListener('click', () => {
    modalTitle.textContent = 'Add Expense';
    expenseForm.reset();
    document.getElementById('expense-id').value = '';
    // Set default date to today
    document.getElementById('expense-date').valueAsDate = new Date();
});

window.editExpense = async (id) => {
    try {
        const res = await fetch(`${API_BASE}/${id}`, { headers: getAuthHeaders() });
        const json = await res.json();
        if (!res.ok) throw new Error(json.error.message);

        const data = json.data;
        document.getElementById('expense-id').value = data.expense_id;
        document.getElementById('expense-date').value = data.expense_date; // Assuming YYYY-MM-DD
        document.getElementById('amount').value = data.amount;
        document.getElementById('category').value = data.category_name;
        document.getElementById('vendor').value = data.vendor_name;
        document.getElementById('payment-method').value = data.payment_method_name;
        document.getElementById('description').value = data.description || '';
        document.getElementById('qty').value = data.qty || 1;
        document.getElementById('unit-price').value = data.unit_price || '';

        modalTitle.textContent = 'Edit Expense';
        expenseModal.show();
    } catch (err) {
        alert('Error fetching expense: ' + err.message);
    }
};

saveBtn.addEventListener('click', async () => {
    const id = document.getElementById('expense-id').value;
    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_BASE}/${id}` : API_BASE;

    const payload = {
        expense_date: document.getElementById('expense-date').value,
        amount: parseFloat(document.getElementById('amount').value),
        category_name: document.getElementById('category').value,
        vendor_name: document.getElementById('vendor').value,
        payment_method_name: document.getElementById('payment-method').value,
        description: document.getElementById('description').value,
        qty: parseInt(document.getElementById('qty').value) || 1,
        unit_price: parseFloat(document.getElementById('unit-price').value) || null
    };

    try {
        const res = await fetch(url, {
            method: method,
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });
        const json = await res.json();

        if (!res.ok) throw new Error(json.error.message);

        expenseModal.hide();
        grid.forceRender(); // Refresh grid
    } catch (err) {
        alert('Error saving: ' + err.message);
    }
});

// Delete
window.deleteExpense = async (id) => {
    if (!confirm('Are you sure you want to delete this expense?')) return;

    try {
        const res = await fetch(`${API_BASE}/${id}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!res.ok) {
            const json = await res.json();
            throw new Error(json.error.message);
        }

        grid.forceRender();
    } catch (err) {
        alert('Error deleting: ' + err.message);
    }
};

// --- AUTOMATED TESTING ---

const testResultsModal = new bootstrap.Modal(document.getElementById('testResultsModal'));
const runTestsBtn = document.getElementById('run-tests-btn');
const testSpinner = document.getElementById('test-spinner');
const testResultsContent = document.getElementById('test-results-content');
const testStatusAlert = document.getElementById('test-status-alert');
const testOutput = document.getElementById('test-output');

runTestsBtn.addEventListener('click', async () => {
    testResultsModal.show();
    testSpinner.classList.remove('d-none');
    testResultsContent.classList.add('d-none');
    testOutput.textContent = '';

    try {
        const res = await fetch('/api/run-tests', {
            method: 'POST',
            headers: getAuthHeaders()
        });
        
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.error?.message || 'Failed to run tests');

        testSpinner.classList.add('d-none');
        testResultsContent.classList.remove('d-none');

        if (data.wasSuccessful) {
            testStatusAlert.className = 'alert alert-success';
            testStatusAlert.textContent = `PASS: Ran ${data.testsRun} tests successfully.`;
        } else {
            testStatusAlert.className = 'alert alert-danger';
            testStatusAlert.textContent = `FAIL: ${data.failures} failures, ${data.errors} errors out of ${data.testsRun} tests.`;
        }

        testOutput.textContent = data.output;

    } catch (err) {
        testSpinner.classList.add('d-none');
        testResultsContent.classList.remove('d-none');
        testStatusAlert.className = 'alert alert-danger';
        testStatusAlert.textContent = 'Error running tests: ' + err.message;
    }
});

// Init
updateUI();
