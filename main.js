const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const net = require('net');

if (!app || typeof app.whenReady !== 'function') {
    console.error('VYOMIX must be started with Electron. Use "npm start" or launch VYOMIX.exe.');
    process.exitCode = 1;
    return;
}

let mainWindow = null;
let backendProcesses = [];
let isQuitting = false;

function getApplicationPaths() {
    const appRoot = app.isPackaged
        ? path.join(process.resourcesPath, 'app')
        : __dirname;
    const pythonRoot = app.isPackaged
        ? process.resourcesPath
        : __dirname;

    return {
        appRoot,
        pythonPath: path.join(pythonRoot, '.venv', 'Scripts', 'python.exe')
    };
}

function checkPort(port) {
    return new Promise((resolve) => {
        const socket = new net.Socket();

        socket.setTimeout(1000);

        socket.once('connect', () => {
            socket.destroy();
            resolve(true);
        });

        socket.once('timeout', () => {
            socket.destroy();
            resolve(false);
        });

        socket.once('error', () => {
            resolve(false);
        });

        socket.connect(port, '127.0.0.1');
    });
}

async function waitForBackend(port, name, backendProcess) {
    console.log(`Waiting for ${name} on port ${port}...`);

    for (let i = 0; i < 60; i++) {
        if (await checkPort(port)) {
            console.log(`${name} is running on port ${port}`);
            return true;
        }

        if (backendProcess && backendProcess.exitCode !== null) {
            throw new Error(
                `${name} exited before opening port ${port} (code ${backendProcess.exitCode}).\n` +
                `${backendProcess.startupError || 'No startup output was captured.'}`
            );
        }

        await new Promise(resolve => setTimeout(resolve, 500));
    }

    throw new Error(
        `${name} did not open port ${port} within 30 seconds.\n` +
        `${backendProcess?.startupError || 'No startup output was captured.'}`
    );
}

function startBackend(application, port, name) {
    const { appRoot, pythonPath } = getApplicationPaths();

    if (!fs.existsSync(pythonPath)) {
        throw new Error(
            `${name} cannot start because Python was not found at:\n${pythonPath}`
        );
    }

    console.log(`Starting ${name}...`);

    const backend = spawn(
        pythonPath,
        [
            '-m',
            'uvicorn',
            application,
            '--host',
            '127.0.0.1',
            '--port',
            String(port)
        ],
        {
            cwd: appRoot,
            env: {
                ...process.env,
                PYTHONPATH: appRoot
            },
            windowsHide: true
        }
    );

    backend.startupError = '';
    backend.stdout.on('data', (data) => {
        const output = data.toString();
        backend.startupError += output;
        console.log(`[${name}] ${output}`);
    });

    backend.stderr.on('data', (data) => {
        const output = data.toString();
        backend.startupError += output;
        console.log(`[${name}] ${output}`);
    });

    backend.on('error', (error) => {
        backend.startupError += `${error.name}: ${error.message}`;
        console.error(`${name} error:`, error);
    });

    backend.on('exit', (code) => {
        console.log(`${name} stopped with code ${code}`);
    });

    backendProcesses.push(backend);

    return backend;
}

async function ensureBackend(application, port, name) {
    if (await checkPort(port)) {
        console.log(`${name} is already running on port ${port}`);
        return null;
    }

    const backend = startBackend(application, port, name);
    await waitForBackend(port, name, backend);
    return backend;
}

function stopBackends() {
    backendProcesses.forEach((backend) => {
        if (!backend || backend.killed || backend.exitCode !== null) {
            return;
        }

        try {
            if (process.platform === 'win32') {
                spawn('taskkill', ['/pid', String(backend.pid), '/T', '/F'], {
                    windowsHide: true,
                    stdio: 'ignore'
                });
            } else {
                backend.kill();
            }
        } catch (error) {
            console.error('Could not stop backend:', error);
        }
    });

    backendProcesses = [];
}

async function createWindow() {

    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1100,
        minHeight: 700,

        backgroundColor: '#071827',

        webPreferences: {
            contextIsolation: false,
            nodeIntegration: true
        }
    });

    /*
       Start VYOMIX backends
    */

    try {
        await ensureBackend('backend.main:app', 8000, 'VYOMIX AUTH');
        await ensureBackend('backend.main2:app', 8003, 'VYOMIX ML');
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`VYOMIX startup failed:\n${message}`);
        dialog.showErrorBox('VYOMIX backend startup failed', message);
        stopBackends();
        app.quit();
        return;
    }

    /*
       Now open VYOMIX
    */

    await mainWindow.loadFile(
        path.join(__dirname, 'index.html')
    );

    mainWindow.show();
    mainWindow.focus();

    console.log('VYOMIX application started successfully!');
}

ipcMain.handle('save-report-pdf', async (event) => {
    const defaultPath = path.join(
        app.getPath('downloads'),
        'vyomix-analysis-report.pdf'
    );
    const saveResult = await dialog.showSaveDialog({
        title: 'Save VYOMIX Report as PDF',
        defaultPath,
        filters: [{ name: 'PDF document', extensions: ['pdf'] }]
    });

    if (saveResult.canceled || !saveResult.filePath) {
        return { success: false, canceled: true };
    }

    const pdf = await event.sender.printToPDF({
        printBackground: true,
        pageSize: 'A4',
        margins: {
            marginType: 'default'
        }
    });
    fs.writeFileSync(saveResult.filePath, pdf);
    return { success: true, filePath: saveResult.filePath };
});

async function startApplication() {
    const hasSingleInstanceLock = app.requestSingleInstanceLock();

    if (!hasSingleInstanceLock) {
        app.quit();
        return;
    }

    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) {
                mainWindow.restore();
            }
            mainWindow.show();
            mainWindow.focus();
        }
    });

    await createWindow();
}

app.whenReady().then(startApplication).catch((error) => {
    const message = error instanceof Error ? error.stack || error.message : String(error);
    console.error(`VYOMIX Electron startup failed:\n${message}`);
    dialog.showErrorBox('VYOMIX startup failed', message);
    stopBackends();
    app.quit();
});

process.on('unhandledRejection', (error) => {
    const message = error instanceof Error ? error.stack || error.message : String(error);
    console.error(`Unhandled VYOMIX startup error:\n${message}`);
});

app.on('before-quit', () => {
    isQuitting = true;
    console.log('Closing VYOMIX...');
    stopBackends();
});

app.on('window-all-closed', () => {

    if (process.platform !== 'darwin' && !isQuitting) {
        app.quit();
    }
});