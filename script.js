// ============================================================
// VYOMIX FRONTEND JAVASCRIPT
// ============================================================


// ============================================================
// BACKEND URLS
// ============================================================

// AUTH BACKEND
// Login + Signup + OTP
const AUTH_API_URL = "http://127.0.0.1:8000";

// ML BACKEND
// Module A + Module B
const ML_API_URL = "http://127.0.0.1:8003";

const SCREENING_STATE_KEY = "vyomixActiveScreening";

const FINAL_STATUS = {
    accepted: "ACCEPTED / PASS",
    review: "REVIEW / AT-RISK",
    rejected: "REJECTED / FAIL"
};

function readScreeningState() {

    try {
        return JSON.parse(localStorage.getItem(SCREENING_STATE_KEY) || "{}") || {};
    } catch (error) {
        console.warn("Unable to read active screening:", error);
        return {};
    }
}

function writeScreeningState(state) {
    localStorage.setItem(SCREENING_STATE_KEY, JSON.stringify(state));
    return state;
}

function screeningFinalStatus(moduleAResult, moduleBResult) {

    if (moduleAResult?.status === "Anomaly" || moduleBResult?.risk === "High") {
        return FINAL_STATUS.rejected;
    }

    if (moduleBResult?.risk === "Review") {
        return FINAL_STATUS.review;
    }

    return FINAL_STATUS.accepted;
}

function moduleAExplanation(result) {
    const score = Number(result?.score ?? result?.anomaly_score);
    const threshold = Number(result?.threshold ?? 348.28);

    if (!Number.isFinite(score)) {
        return result?.explanation || "Module A could not calculate an anomaly score for this component.";
    }

    if (result?.status === "Anomaly") {
        return `Anomaly score ${score.toFixed(2)} exceeds the population threshold of ${threshold.toFixed(2)}. The component shows abnormal lot-relative behaviour and requires attention.`;
    }

    return `Anomaly score ${score.toFixed(2)} is below the population threshold of ${threshold.toFixed(2)}. No significant dynamic anomaly detected.`;
}

function moduleBExplanation(result) {
    if (!result) {
        return "No Module B prediction was saved for this component.";
    }

    if (result.error) {
        return `Module B could not complete the prediction: ${result.error}`;
    }

    const measurements = result.measurements || {};
    const predicted = result.predicted_168h
        ?? measurements.predicted_168h
        ?? result.predictions?.RDSon_mOhm_168h
        ?? result.score;
    const drift = Number(measurements.drift);
    const predictedText = Number.isFinite(Number(predicted))
        ? Number(predicted).toFixed(4)
        : "unavailable";
    const driftText = Number.isFinite(drift)
        ? ` Drift relative to the 0h measurement is ${drift.toFixed(2)}%.`
        : "";

    if (result.risk === "High") {
        return `Predicted 168h value is ${predictedText} and the Module B model classified the component as high risk.${driftText} Component requires engineering review.`;
    }

    if (result.risk === "Review") {
        return `Predicted 168h value is ${predictedText}, but the Module B prediction requires review.${driftText} Component requires engineering review.`;
    }

    return `Predicted 168h value is ${predictedText}. The Module B forecast shows no significant future drift.${driftText}`;
}

function finalDecisionReason(moduleAResult, moduleBResult, status) {
    const moduleAConcern = moduleAResult?.status === "Anomaly";
    const moduleBConcern = moduleBResult?.risk === "High" || moduleBResult?.risk === "Review";

    if (status === FINAL_STATUS.rejected) {
        const reasons = [];
        if (moduleAConcern) reasons.push("Module A detected a significant dynamic anomaly");
        if (moduleBResult?.risk === "High") reasons.push("Module B predicts high 168h risk");
        return `${reasons.join(" and ")}. The component is classified as high risk and should be rejected according to the existing screening rules.`;
    }

    if (status === FINAL_STATUS.review || moduleBConcern) {
        if (moduleAConcern) {
            return "Module A detected a dynamic anomaly and Module B also requires attention. Component requires engineering review.";
        }
        return "Module A is within the acceptable range, but Module B requires attention for the 168h prediction. Component requires engineering review.";
    }

    return "Module A detected no significant anomaly and Module B predicts no significant 168h risk. Component can be accepted.";
}

function buildScreeningResults(moduleA, moduleB) {

    const moduleBById = new Map(
        (moduleB || []).map(result => [result.component_id, result])
    );

    return (moduleA || []).map(moduleAResult => {
        const moduleBResult = moduleBById.get(moduleAResult.component_id) || {};
        return {
            component_id: moduleAResult.component_id,
            module_a: moduleAResult,
            module_b: moduleBResult,
            status: screeningFinalStatus(moduleAResult, moduleBResult),
            score: moduleAResult.score ?? moduleAResult.anomaly_score ?? null,
            module_a_explanation: moduleAExplanation(moduleAResult),
            module_b_explanation: moduleBExplanation(moduleBResult),
            reason: finalDecisionReason(
                moduleAResult,
                moduleBResult,
                screeningFinalStatus(moduleAResult, moduleBResult)
            ),
            explanation: finalDecisionReason(
                moduleAResult,
                moduleBResult,
                screeningFinalStatus(moduleAResult, moduleBResult)
            )
        };
    });
}

async function persistCompletedScreening(state) {

    const finalResults = buildScreeningResults(state.moduleA, state.moduleB);
    const passCount = finalResults.filter(result => result.status === FINAL_STATUS.accepted).length;
    const reviewCount = finalResults.filter(result => result.status === FINAL_STATUS.review).length;
    const failedCount = finalResults.filter(result => result.status === FINAL_STATUS.rejected).length;
    const moduleAAnomalyCount = (state.moduleA || [])
        .filter(result => result.status === "Anomaly")
        .length;
    const moduleBAtRiskCount = (state.moduleB || [])
        .filter(result => result.risk === "High" || result.risk === "Review")
        .length;
    const user = JSON.parse(localStorage.getItem("vyomixUser") || "{}");

    const response = await fetch(`${AUTH_API_URL}/screenings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            screening_id: state.screeningId,
            user_email: user.email || "anonymous",
            filename: state.filename || "screening.csv",
            total_components: finalResults.length,
            pass_count: passCount,
            monitor_count: reviewCount,
            reject_count: failedCount,
            module_a_anomaly_count: moduleAAnomalyCount,
            module_b_at_risk_count: moduleBAtRiskCount,
            review_count: reviewCount,
            failed_count: failedCount,
            module_a: state.moduleA || [],
            module_b: state.moduleB || [],
            results: finalResults
        })
    });
    const data = await getResponseData(response);

    if (!response.ok || !data.success) {
        throw new Error(getErrorMessage(data, "Completed screening could not be saved."));
    }

    state.screeningId = data.screening_id;
    state.results = finalResults;
    state.total = finalResults.length;
    state.pass = passCount;
    state.review = reviewCount;
    state.failed = failedCount;
    state.moduleAAnomalies = moduleAAnomalyCount;
    state.moduleBAtRisk = moduleBAtRiskCount;
    state.completedAt = data.created_at;
    writeScreeningState(state);
    return state;
}

window.vyomixStoreModuleA = function (data, filename) {

    const state = readScreeningState();
    state.screeningId = state.screeningId || `SCR-${Date.now()}`;
    state.filename = filename || state.filename || "screening.csv";
    state.moduleA = data.results || [];
    state.moduleATotal = data.total_components || state.moduleA.length;
    state.moduleAAnomalies = data.anomaly_components || 0;
    writeScreeningState(state);
    return state;
};

window.vyomixStoreModuleB = async function (data, filename) {

    const state = readScreeningState();
    state.screeningId = state.screeningId || `SCR-${Date.now()}`;
    state.filename = filename || state.filename || "screening.csv";
    state.moduleB = data.results || [];
    state.moduleBAtRisk = data.high_risk_count || 0;
    writeScreeningState(state);

    if (state.moduleA?.length) {
        return persistCompletedScreening(state);
    }

    return state;
};


// ============================================================
// HELPER — SAFE JSON RESPONSE
// ============================================================

async function getResponseData(response) {

    try {

        return await response.json();

    } catch (error) {

        return {
            success: false,
            message: "Server returned an invalid response."
        };

    }

}


// ============================================================
// HELPER — ERROR MESSAGE
// ============================================================

function getErrorMessage(data, fallback) {

    return (
        data?.detail ||
        data?.message ||
        data?.error ||
        fallback
    );

}


// ============================================================
// LOAD LOGGED-IN USER
// ============================================================

function loadLoggedInUser() {

    const savedUser =
        localStorage.getItem("vyomixUser");

    if (!savedUser) {
        return;
    }

    try {

        const user =
            JSON.parse(savedUser);

        const name =
            user.name || "User";

        const role =
            user.role || "Engineer";

        const email =
            user.email ||
            localStorage.getItem("vyomixEmail") ||
            "—";


        // USER NAME

        document
            .querySelectorAll("#userName")
            .forEach(function (element) {

                element.textContent = name;

            });


        // USER ROLE

        document
            .querySelectorAll("#userRole")
            .forEach(function (element) {

                element.textContent = role;

            });


        // WELCOME NAME

        document
            .querySelectorAll("#welcomeName")
            .forEach(function (element) {

                element.textContent = name;

            });


        // USER AVATAR

        document
            .querySelectorAll("#userAvatar")
            .forEach(function (element) {

                element.textContent =
                    name.charAt(0).toUpperCase();

            });


        // SETTINGS EMAIL

        document
            .querySelectorAll("#settingsEmail")
            .forEach(function (element) {

                element.textContent = email;

            });


        // SETTINGS NAME

        document
            .querySelectorAll("#settingsName")
            .forEach(function (element) {

                element.textContent = name;

            });


        // SETTINGS ROLE

        document
            .querySelectorAll("#settingsRole")
            .forEach(function (element) {

                element.textContent = role;

            });

    }

    catch (error) {

        console.error(
            "Unable to load logged-in user:",
            error
        );

    }

}


// Run user loader

loadLoggedInUser();


// ============================================================
// LOGIN PAGE
// ============================================================

const loginForm =
    document.getElementById("loginForm");


if (loginForm) {

    loginForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const loginId =
                document
                    .getElementById("loginId")
                    ?.value
                    .trim();


            const password =
                document
                    .getElementById("password")
                    ?.value;


            // CHECK FIELDS

            if (!loginId || !password) {

                alert(
                    "Please enter your login details."
                );

                return;

            }


            try {

                // =================================================
                // LOGIN → AUTH BACKEND :8000
                // =================================================

                const response =
                    await fetch(
                        `${AUTH_API_URL}/login`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                login_id:
                                    loginId,

                                password:
                                    password

                            })

                        }
                    );


                const data =
                    await getResponseData(
                        response
                    );


                // LOGIN FAILED

                if (
                    !response.ok ||
                    !data.success
                ) {

                    alert(
                        getErrorMessage(
                            data,
                            "Login failed. Please check your credentials."
                        )
                    );

                    return;

                }


                // =================================================
                // SAVE USER
                // =================================================

                if (data.user) {

                    localStorage.setItem(
                        "vyomixUser",
                        JSON.stringify(data.user)
                    );


                    if (data.user.email) {

                        localStorage.setItem(
                            "vyomixEmail",
                            data.user.email
                        );

                    }

                }


                // =================================================
                // SEND OTP → AUTH BACKEND :8000
                // =================================================

                const userEmail =
                    data.user?.email ||
                    localStorage.getItem(
                        "vyomixEmail"
                    );


                if (!userEmail) {

                    alert(
                        "Login successful, but registered email was not found."
                    );

                    return;

                }


                const otpResponse =
                    await fetch(
                        `${AUTH_API_URL}/send-otp`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                email:
                                    userEmail

                            })

                        }
                    );


                const otpData =
                    await getResponseData(
                        otpResponse
                    );


                if (
                    otpResponse.ok &&
                    otpData.success
                ) {

                    alert(
                        "Login successful!\n\n" +
                        "OTP has been sent to your registered email."
                    );


                    window.location.href =
                        "otp.html";

                    return;

                }


                alert(
                    "Login successful, but OTP could not be sent.\n\n" +
                    getErrorMessage(
                        otpData,
                        "Please try again."
                    )
                );

            }

            catch (error) {

                console.error(
                    "Login error:",
                    error
                );


                alert(
                    "Unable to connect to VYOMIX authentication server.\n\n" +
                    "Make sure the Auth FastAPI server is running on port 8000."
                );

            }

        }
    );

}


// ============================================================
// SIGNUP PAGE
// ============================================================

const signupForm =
    document.getElementById("signupForm");


if (signupForm) {

    signupForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const fullName =
                document
                    .getElementById("fullName")
                    ?.value
                    .trim();


            const employeeId =
                document
                    .getElementById("employeeId")
                    ?.value
                    .trim();


            const email =
                document
                    .getElementById("email")
                    ?.value
                    .trim()
                    .toLowerCase();


            const role =
                document
                    .getElementById("role")
                    ?.value;


            const password =
                document
                    .getElementById("signupPassword")
                    ?.value;


            const confirmPassword =
                document
                    .getElementById("confirmPassword")
                    ?.value;


            // CHECK FIELDS

            if (
                !fullName ||
                !employeeId ||
                !email ||
                !role ||
                !password ||
                !confirmPassword
            ) {

                alert(
                    "Please fill in all the fields."
                );

                return;

            }


            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {

                alert(
                    "Please enter a valid email address, for example name@example.com."
                );

                document
                    .getElementById("email")
                    ?.focus();

                return;

            }


            // PASSWORD CHECK

            if (password !== confirmPassword) {

                alert(
                    "Passwords do not match."
                );

                return;

            }


            try {

                // =================================================
                // SIGNUP → AUTH BACKEND :8000
                // =================================================

                const response =
                    await fetch(
                        `${AUTH_API_URL}/signup`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                name:
                                    fullName,

                                employee_id:
                                    employeeId,

                                email:
                                    email,

                                password:
                                    password,

                                role:
                                    role

                            })

                        }
                    );


                const data =
                    await getResponseData(
                        response
                    );


                if (
                    response.ok &&
                    data.success
                ) {

                    localStorage.setItem(
                        "vyomixEmail",
                        email
                    );


                    alert(
                        "Account created successfully!\n\n" +
                        "Please login to receive your OTP."
                    );


                    window.location.href =
                        "index.html";

                    return;

                }


                alert(
                    getErrorMessage(
                        data,
                        "Unable to create the account."
                    )
                );

            }

            catch (error) {

                console.error(
                    "Signup error:",
                    error
                );


                alert(
                    "Unable to connect to VYOMIX authentication server.\n\n" +
                    "Make sure FastAPI is running on port 8000."
                );

            }

        }
    );

}


// ============================================================
// OTP PAGE — SHOW EMAIL
// ============================================================

const otpEmail =
    document.getElementById("otpEmail");


if (otpEmail) {

    const email =
        localStorage.getItem(
            "vyomixEmail"
        );


    otpEmail.textContent =
        email ||
        "your registered email";

}


// ============================================================
// OTP INPUT BOXES
// ============================================================

const otpBoxes =
    document.querySelectorAll(
        ".otp-box"
    );


if (otpBoxes.length > 0) {

    otpBoxes.forEach(
        function (box, index) {


            // ONLY NUMBERS

            box.addEventListener(
                "input",
                function () {

                    this.value =
                        this.value
                            .replace(
                                /[^0-9]/g,
                                ""
                            )
                            .slice(0, 1);


                    if (
                        this.value &&
                        index <
                        otpBoxes.length - 1
                    ) {

                        otpBoxes[
                            index + 1
                        ].focus();

                    }

                }
            );


            // BACKSPACE

            box.addEventListener(
                "keydown",
                function (event) {

                    if (
                        event.key ===
                        "Backspace" &&
                        !this.value &&
                        index > 0
                    ) {

                        otpBoxes[
                            index - 1
                        ].focus();

                    }

                }
            );


            // PASTE OTP

            box.addEventListener(
                "paste",
                function (event) {

                    event.preventDefault();


                    const pastedData =
                        event.clipboardData
                            .getData("text")
                            .replace(
                                /[^0-9]/g,
                                ""
                            )
                            .slice(
                                0,
                                otpBoxes.length
                            );


                    pastedData
                        .split("")
                        .forEach(
                            function (
                                digit,
                                i
                            ) {

                                if (
                                    otpBoxes[i]
                                ) {

                                    otpBoxes[i]
                                        .value =
                                        digit;

                                }

                            }
                        );


                    if (
                        pastedData.length > 0
                    ) {

                        const focusIndex =
                            Math.min(
                                pastedData.length,
                                otpBoxes.length
                            ) - 1;


                        otpBoxes[
                            focusIndex
                        ].focus();

                    }

                }
            );

        }
    );

}


// ============================================================
// VERIFY OTP
// ============================================================

const verifyButton =
    document.getElementById(
        "verifyOtp"
    );


if (verifyButton) {

    verifyButton.addEventListener(
        "click",
        async function () {


            let otp = "";


            otpBoxes.forEach(
                function (box) {

                    otp += box.value;

                }
            );


            if (
                otp.length !==
                otpBoxes.length
            ) {

                alert(
                    "Please enter the complete 6-digit OTP."
                );

                return;

            }


            const email =
                localStorage.getItem(
                    "vyomixEmail"
                );


            if (!email) {

                alert(
                    "Email information not found.\n\n" +
                    "Please login again."
                );


                window.location.href =
                    "index.html";

                return;

            }


            try {

                // =================================================
                // VERIFY OTP → AUTH BACKEND :8000
                // =================================================

                const response =
                    await fetch(
                        `${AUTH_API_URL}/verify-otp`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                email:
                                    email,

                                otp:
                                    otp

                            })

                        }
                    );


                const data =
                    await getResponseData(
                        response
                    );


                if (
                    response.ok &&
                    data.success
                ) {

                    alert(
                        "OTP verified successfully!"
                    );


                    window.location.href =
                        "dashboard.html";

                    return;

                }


                alert(
                    getErrorMessage(
                        data,
                        "Invalid or expired OTP."
                    )
                );

            }

            catch (error) {

                console.error(
                    "OTP verification error:",
                    error
                );


                alert(
                    "Unable to connect to VYOMIX authentication server."
                );

            }

        }
    );

}


// ============================================================
// OTP COUNTDOWN
// ============================================================

const timer =
    document.getElementById(
        "timer"
    );


const resendButton =
    document.getElementById(
        "resendOtp"
    );


if (timer) {

    let timeLeft =
        5 * 60;


    const countdown =
        setInterval(
            function () {


                const minutes =
                    Math.floor(
                        timeLeft / 60
                    );


                const seconds =
                    timeLeft % 60;


                timer.textContent =
                    String(
                        minutes
                    ).padStart(
                        2,
                        "0"
                    )
                    +
                    ":"
                    +
                    String(
                        seconds
                    ).padStart(
                        2,
                        "0"
                    );


                if (
                    timeLeft <= 0
                ) {

                    clearInterval(
                        countdown
                    );


                    timer.textContent =
                        "Expired";


                    if (resendButton) {

                        resendButton.disabled =
                            false;

                    }


                    return;

                }


                timeLeft--;

            },
            1000
        );

}


// ============================================================
// RESEND OTP
// ============================================================

if (resendButton) {

    resendButton.addEventListener(
        "click",
        async function () {


            const email =
                localStorage.getItem(
                    "vyomixEmail"
                );


            if (!email) {

                alert(
                    "Email information not found.\n\n" +
                    "Please login again."
                );


                window.location.href =
                    "index.html";

                return;

            }


            try {

                resendButton.disabled =
                    true;


                // AUTH BACKEND :8000

                const response =
                    await fetch(
                        `${AUTH_API_URL}/send-otp`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                email:
                                    email

                            })

                        }
                    );


                const data =
                    await getResponseData(
                        response
                    );


                if (
                    response.ok &&
                    data.success
                ) {

                    alert(
                        "A new OTP has been sent to your email."
                    );


                    location.reload();

                    return;

                }


                resendButton.disabled =
                    false;


                alert(
                    getErrorMessage(
                        data,
                        "Unable to resend OTP."
                    )
                );

            }

            catch (error) {

                console.error(
                    "Resend OTP error:",
                    error
                );


                resendButton.disabled =
                    false;


                alert(
                    "Unable to connect to VYOMIX authentication server."
                );

            }

        }
    );

}


// ============================================================
// LOGOUT
// ============================================================

document
    .querySelectorAll(
        "#logoutButton"
    )
    .forEach(
        function (button) {

            button.addEventListener(
                "click",
                function () {


                    localStorage.removeItem(
                        "vyomixUser"
                    );


                    localStorage.removeItem(
                        "vyomixEmail"
                    );


                    location.reload();

                }
            );

        }
    );


// ============================================================
// MODULE A — JSON API
// ============================================================

async function callModuleA(values) {

    try {

        const response =
            await fetch(
                `${ML_API_URL}/module-a`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        values:
                            values

                    })

                }
            );


        const data =
            await getResponseData(
                response
            );


        console.log(
            "Module A backend result:",
            data
        );


        if (
            !response.ok ||
            !data.success
        ) {

            throw new Error(
                getErrorMessage(
                    data,
                    "Module A request failed."
                )
            );

        }


        return data;

    }

    catch (error) {

        console.error(
            "Module A error:",
            error
        );

        throw error;

    }

}


// ============================================================
// MODULE A — CSV UPLOAD API
// ============================================================

async function analyzeModuleACSV(csvFile) {

    if (!csvFile) {

        throw new Error(
            "Please select a CSV file."
        );

    }


    const formData =
        new FormData();


    // IMPORTANT:
    // "file" must match the FastAPI parameter

    formData.append(
        "file",
        csvFile
    );


    console.log(
        "Sending Module A CSV:",
        csvFile.name
    );


    try {

        const response =
            await fetch(
                `${ML_API_URL}/module-a/analyze`,
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await getResponseData(
                response
            );


        console.log(
            "Module A CSV result:",
            data
        );


        if (
            !response.ok ||
            !data.success
        ) {

            throw new Error(
                getErrorMessage(
                    data,
                    "Module A CSV analysis failed."
                )
            );

        }


        return data;

    }

    catch (error) {

        console.error(
            "Module A CSV error:",
            error
        );

        throw error;

    }

}


// ============================================================
// MODULE B — JSON API
// ============================================================

async function callModuleB(values) {

    try {

        const response =
            await fetch(
                `${ML_API_URL}/module-b`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        values:
                            values

                    })

                }
            );


        const data =
            await getResponseData(
                response
            );


        console.log(
            "Module B backend result:",
            data
        );


        if (
            !response.ok ||
            !data.success
        ) {

            throw new Error(
                getErrorMessage(
                    data,
                    "Module B request failed."
                )
            );

        }


        return data;

    }

    catch (error) {

        console.error(
            "Module B error:",
            error
        );

        throw error;

    }

}


// ============================================================
// END OF VYOMIX JAVASCRIPT
// ============================================================