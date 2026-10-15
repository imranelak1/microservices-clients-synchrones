"""Exécuter les appels réels, mesurer les processus et observer les pannes du lab."""

import asyncio, csv, gzip, json, math, os, platform, shutil, statistics, subprocess, time, urllib.request, urllib.error
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parents[1]
MODE = os.environ.get("DISCOVERY_MODE", "eureka")
SMOKE = os.environ.get("SMOKE", "false").lower() == "true"
RUN_ID = (
    os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
    + "-"
    + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
)
HERE = ROOT / ".benchmark-work" / MODE / RUN_ID
HERE.mkdir(parents=True, exist_ok=True)
REPO = ROOT
RESULT = ROOT / "results" / ("remote-" + MODE + ("-smoke" if SMOKE else "")) / RUN_ID
RESULT.mkdir(parents=True, exist_ok=True)
ART = HERE / "artifacts"
JMETER = (
    Path(os.environ.get("JMETER_HOME", "/opt/apache-jmeter-5.6.3"))
    / "bin/ApacheJMeter.jar"
)
STATE = HERE / "state.json"
CREATE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
METHODS = ["rest", "feign", "webclient"]


def save(s):
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def req(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def ready(url, timeout=180, check=lambda x: True):
    until = time.monotonic() + timeout
    last = None
    while time.monotonic() < until:
        try:
            value = req(url)
            if check(value):
                return value
        except Exception as e:
            last = e
        time.sleep(1)
    raise RuntimeError(str(url) + " not ready: " + str(last))


def spawn(role, mode):
    s = state()
    env = os.environ.copy()
    env.update(
        DISCOVERY=mode,
        EUREKA_URL="http://127.0.0.1:19261/eureka/",
        CONSUL_PORT="19260",
        SERVICE_IP="127.0.0.1",
    )
    module = {
        "client": "service-client",
        "car": "service-voiture",
        "discovery": "eureka-server",
    }[role]
    port = {"client": 19263, "car": 19262, "discovery": 19261}[role]
    command = [
        "java",
        "-Xmx160m",
        "-Xss512k",
        "-XX:MaxMetaspaceSize=160m",
        "-XX:ActiveProcessorCount=2",
        "-Dhttp.maxConnections=500",
        "-Duser.timezone=UTC",
        "-jar",
        str(ART / mode / (module + ".jar")),
        "--server.port=" + str(port),
        "--debug=false",
    ]
    if role == "discovery" and mode == "consul":
        command = [
            "/opt/consul/consul",
            "agent",
            "-dev",
            "-client=127.0.0.1",
            "-bind=127.0.0.1",
            "-http-port=19260",
        ]
    log = HERE / (mode + "-" + role + "-" + str(int(time.time())) + ".log")
    with log.open("w", encoding="utf-8") as output:
        p = subprocess.Popen(
            command,
            cwd=REPO,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=CREATE,
        )
    s.setdefault("processes", {})[role] = {
        "pid": p.pid,
        "command": command,
        "log": str(log),
        "started": time.time(),
        "discovery_settings": {
            k: env[k] for k in ["DISCOVERY", "EUREKA_URL", "CONSUL_PORT", "SERVICE_IP"]
        },
    }
    s["mode"] = mode
    save(s)
    print("START", mode, role, p.pid, flush=True)
    return p.pid


def stop(role):
    s = state()
    item = s.get("processes", {}).get(role)
    if item:
        try:
            p = psutil.Process(item["pid"])
            if str(ART).lower() not in " ".join(p.cmdline()).lower() and not (
                item["command"][0] == "/opt/consul/consul"
                and p.cmdline()[0] == "/opt/consul/consul"
            ):
                raise RuntimeError("PID does not belong to this isolated lab")
            p.terminate()
            try:
                p.wait(20)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(10)
        except psutil.NoSuchProcess:
            pass
        s["processes"].pop(role)
        save(s)
        print("STOP", role, item["pid"], flush=True)


def registered(mode):
    if mode == "eureka":
        for name in ["SERVICE-CLIENT", "SERVICE-VOITURE"]:
            request = urllib.request.Request(
                "http://127.0.0.1:19261/eureka/apps/" + name,
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                value = json.load(response)
            instances = value["application"]["instance"]
            instances = instances if isinstance(instances, list) else [instances]
            if not any(x["status"] == "UP" for x in instances):
                return False
    else:
        for name in ["SERVICE-CLIENT", "SERVICE-VOITURE"]:
            if not req(
                "http://127.0.0.1:19260/v1/health/service/" + name + "?passing=true"
            ):
                return False
    return True


def wait_registered(mode, timeout=150):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if registered(mode):
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Registration did not become healthy in " + mode)


def verify(mode):
    ready("http://127.0.0.1:19262/actuator/health")
    ready("http://127.0.0.1:19263/actuator/health")
    wait_registered(mode)
    baseline = req("http://127.0.0.1:19262/api/cars/byClient/1")
    results = {}
    for method in METHODS:
        value = ready(
            "http://127.0.0.1:19263/api/clients/1/car/" + method,
            check=lambda v: v == baseline,
        )
        results[method] = {
            "id": value["id"],
            "clientId": value["clientId"],
            "payload_bytes": len(json.dumps(value, separators=(",", ":")).encode()),
            "details_length": len(value["details"]),
        }
    (RESULT / (mode + "-functional.json")).write_text(
        json.dumps(
            {
                "mode": mode,
                "registered": True,
                "verified_at": time.time(),
                "responses": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("VERIFIED", mode, json.dumps(results), flush=True)


def start(mode):
    s = state()
    if s.get("processes"):
        raise RuntimeError("Stop this lab before switching modes")
    spawn("discovery", mode)
    ready(
        "http://127.0.0.1:19261/actuator/health"
        if mode == "eureka"
        else "http://127.0.0.1:19260/v1/status/leader"
    )
    spawn("car", mode)
    spawn("client", mode)
    verify(mode)


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)]


def benchmark(mode, method):
    if state().get("mode") != mode:
        raise RuntimeError("Wrong active discovery")
    verify(mode)
    # Equal short warm-up of the selected endpoint before each measurement.
    for _ in range(50):
        req("http://127.0.0.1:19263/api/clients/1/car/" + method)
    raw = HERE / (mode + "-" + method + ".jtl")
    if raw.exists():
        raise RuntimeError("Refusing to overwrite real measurements: " + str(raw))
    cmd = [
        "java",
        "-Xmx192m",
        "-Xss256k",
        "-XX:ActiveProcessorCount=2",
        "-jar",
        str(JMETER),
        "-n",
        "-t",
        str(REPO / "loadtests/clients.jmx"),
        "-l",
        str(raw),
        "-j",
        str(HERE / (mode + "-" + method + "-jmeter.log")),
        "-Jmethod=" + method,
        "-Jport=19263",
        "-Jhost=127.0.0.1",
    ]
    if SMOKE:
        cmd += [
            "-Jduration=2",
            "-JrampUp=1",
            *["-Jthreads" + str(i) + "=" + str(i) for i in range(1, 6)],
        ]
    procs = {
        role: psutil.Process(item["pid"])
        for role, item in state()["processes"].items()
        if role in ["client", "car"]
    }
    for p in procs.values():
        p.cpu_percent()
    rows = []
    log = RESULT / (mode + "-" + method + "-jmeter-output.txt")
    print("BENCH START", mode, method, time.strftime("%H:%M:%S"), flush=True)
    with log.open("w", encoding="utf-8") as output:
        p = subprocess.Popen(
            cmd, cwd=HERE, stdout=output, stderr=subprocess.STDOUT, creationflags=CREATE
        )
        while p.poll() is None:
            time.sleep(1)
            now = time.time()
            for role, process in procs.items():
                try:
                    cpu = process.cpu_percent()
                    rss = process.memory_info().rss
                except psutil.NoSuchProcess:
                    raise RuntimeError(role + " process terminated during benchmark")
                rows.append(
                    {
                        "timestamp_ms": round(now * 1000),
                        "discovery": mode,
                        "method": method,
                        "service": role,
                        "cpu_one_core_percent": round(cpu, 2),
                        "cpu_machine_percent": round(cpu / psutil.cpu_count(), 2),
                        "rss_mib": round(rss / 1048576, 2),
                    }
                )
    if p.returncode:
        raise RuntimeError("JMeter exited " + str(p.returncode) + ": " + str(log))
    groups = {}
    # Stream the JTL so the summarizer does not retain hundreds of thousands of dictionaries.
    with raw.open(encoding="utf-8") as source:
        for sample in csv.DictReader(source):
            users = int(sample["threadName"].split()[0])
            elapsed = int(sample["elapsed"])
            began = int(sample["timeStamp"])
            group = groups.setdefault(
                users,
                {"lat": [], "success_lat": [], "first": began, "last": began + elapsed},
            )
            group["lat"].append(elapsed)
            if sample["success"].lower() == "true":
                group["success_lat"].append(elapsed)
            group["first"] = min(group["first"], began)
            group["last"] = max(group["last"], began + elapsed)
    summary = []
    for users, group in sorted(groups.items()):
        lat = group["lat"]
        success_lat = group["success_lat"]
        first = group["first"]
        last = group["last"]
        count = len(lat)
        successes = len(success_lat)
        entry = {
            "discovery": mode,
            "method": method,
            "users": users,
            "requests": count,
            "errors": count - successes,
            "error_percent": round(100 * (count - successes) / count, 3),
            "mean_ms": round(statistics.mean(lat), 2),
            "p95_ms": percentile(lat, 0.95),
            "requests_per_second": round(count / ((last - first) / 1000), 2),
            "successful_requests_per_second": round(
                successes / ((last - first) / 1000), 2
            ),
            "success_mean_ms": (
                round(statistics.mean(success_lat), 2) if success_lat else None
            ),
            "success_p95_ms": percentile(success_lat, 0.95) if success_lat else None,
            "duration_seconds": round((last - first) / 1000, 3),
        }
        for role in procs:
            resource = [
                x
                for x in rows
                if x["service"] == role and first <= x["timestamp_ms"] <= last
            ]
            entry[role + "_cpu_machine_mean_percent"] = round(
                statistics.mean(x["cpu_machine_percent"] for x in resource), 2
            )
            entry[role + "_rss_peak_mib"] = max(x["rss_mib"] for x in resource)
        summary.append(entry)
    if sorted(groups) != ([1, 2, 3, 4, 5] if SMOKE else [10, 50, 100, 200, 500]):
        raise RuntimeError("Missing JMeter load groups: " + str(groups.keys()))
    write_csv(RESULT / (mode + "-" + method + "-resources.csv"), rows)
    (RESULT / (mode + "-" + method + "-summary.json")).write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (
        raw.open("rb") as source,
        gzip.open(RESULT / (mode + "-" + method + ".jtl.gz"), "wb") as dest,
    ):
        shutil.copyfileobj(source, dest)
    allrows = []
    for file in sorted(RESULT.glob("*-summary.json")):
        allrows.extend(json.loads(file.read_text(encoding="utf-8")))
    write_csv(RESULT / "performance.csv", allrows)
    print("BENCH COMPLETE", mode, method, json.dumps(summary), flush=True)


def write_csv(path, rows):
    if not rows:
        raise RuntimeError("No records for " + str(path))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


async def fault(mode, role):
    import aiohttp

    verify(mode)
    events = []
    rows = []
    starttime = time.monotonic()
    outage_at = 5
    restart_at = 20
    total = 65

    async def lifecycle():
        await asyncio.sleep(outage_at)
        await asyncio.to_thread(stop, role)
        events.append(
            {
                "event": "stopped",
                "elapsed_seconds": time.monotonic() - starttime,
                "time": time.time(),
            }
        )
        await asyncio.sleep(max(0, restart_at - (time.monotonic() - starttime)))
        events.append(
            {
                "event": "restart_requested",
                "elapsed_seconds": time.monotonic() - starttime,
                "time": time.time(),
            }
        )
        await asyncio.to_thread(spawn, role, mode)

    async def call(session, index):
        method = METHODS[index % 3]
        t = time.monotonic()
        status = 0
        error = ""
        try:
            async with session.get(
                "http://127.0.0.1:19263/api/clients/1/car/" + method
            ) as response:
                status = response.status
                body = await response.json()
                if status == 200 and (
                    body.get("id") != 10 or len(body.get("details", "")) != 3000
                ):
                    error = "payload"
        except Exception as e:
            error = type(e).__name__
        rows.append(
            {
                "discovery": mode,
                "fault": role,
                "method": method,
                "start_seconds": round(t - starttime, 3),
                "elapsed_ms": round((time.monotonic() - t) * 1000, 2),
                "status": status,
                "success": status == 200 and not error,
                "error": error,
            }
        )

    connector = aiohttp.TCPConnector(limit=600, limit_per_host=600)
    async with aiohttp.ClientSession(
        connector=connector, timeout=aiohttp.ClientTimeout(total=7)
    ) as session:
        life = asyncio.create_task(lifecycle())
        tasks = []
        for index in range(total * 100):
            await asyncio.sleep(max(0, index / 100 - (time.monotonic() - starttime)))
            tasks.append(asyncio.create_task(call(session, index)))
        await asyncio.gather(*tasks)
        await life
    write_csv(
        RESULT / (mode + "-fault-" + role + ".csv"),
        sorted(rows, key=lambda x: x["start_seconds"]),
    )
    summaries = []
    for method in METHODS:
        selected = [r for r in rows if r["method"] == method]
        failed = [r for r in selected if not r["success"]]
        first_recovered = next(
            (
                r["start_seconds"]
                for r in sorted(selected, key=lambda r: r["start_seconds"])
                if r["start_seconds"] >= restart_at and r["success"]
            ),
            None,
        )
        during = [r for r in selected if outage_at <= r["start_seconds"] < restart_at]
        summaries.append(
            {
                "method": method,
                "requests": len(selected),
                "errors": len(failed),
                "error_percent": round(100 * len(failed) / len(selected), 2),
                "outage_window_error_percent": round(
                    100 * sum(not r["success"] for r in during) / len(during), 2
                ),
                "first_success_after_restart_seconds": (
                    None
                    if first_recovered is None
                    else round(first_recovered - restart_at, 3)
                ),
                "max_elapsed_ms": max(r["elapsed_ms"] for r in selected),
            }
        )
    try:
        registration_ok = await asyncio.to_thread(registered, mode)
    except Exception:
        registration_ok = False
    data = {
        "mode": mode,
        "fault": role,
        "target_rate_total_rps": 100,
        "duration_seconds": total,
        "events": events,
        "methods": summaries,
        "registered_after_restart": registration_ok,
    }
    if not registration_ok:
        # A dev discovery server may lose registrations across its own restart.
        # Record that outcome before explicitly repairing the lab for the next scenario.
        data["manual_recovery"] = (
            "Restart both application processes to register them again."
        )
        await asyncio.to_thread(stop, "client")
        await asyncio.to_thread(stop, "car")
        await asyncio.to_thread(spawn, "car", mode)
        await asyncio.to_thread(spawn, "client", mode)
    await asyncio.to_thread(verify, mode)
    data["healthy_after_scenario_cleanup"] = True
    (RESULT / (mode + "-fault-" + role + "-summary.json")).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    print("FAULT COMPLETE", json.dumps(data), flush=True)


def stop_all():
    for role in ["client", "car", "discovery"]:
        stop(role)


def environment(mode):
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None

    data = {
        "mode": mode,
        "smoke": SMOKE,
        "platform": platform.platform(),
        "logical_cpus": psutil.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
        "host_ram_mib": round(psutil.virtual_memory().total / 1048576),
        "cgroup_memory_max": read("/sys/fs/cgroup/memory.max"),
        "cgroup_cpu_max": read("/sys/fs/cgroup/cpu.max"),
        "jvm_flags": [
            "-Xmx160m",
            "-Xss512k",
            "-XX:MaxMetaspaceSize=160m",
            "-XX:ActiveProcessorCount=2",
            "-Dhttp.maxConnections=500",
        ],
        "jmeter_heap": "192m",
        "users": [1, 2, 3, 4, 5] if SMOKE else [10, 50, 100, 200, 500],
        "duration_per_level_seconds": 2 if SMOKE else 30,
        "ramp_seconds": 1 if SMOKE else 10,
        "warmup_requests": 50,
        "registered_service_address": "127.0.0.1",
        "response_json_bytes": 3070,
        "car_delay_ms": 20,
        "fresh_full_stack_per_method": True,
        "fault_rate_total_rps": 100,
        "fault_stop_seconds": 15,
        "java": subprocess.run(
            ["java", "-version"], capture_output=True, text=True
        ).stderr,
    }
    (RESULT / (mode + "-environment.json")).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def main():
    mode = MODE
    if mode not in ["eureka", "consul"]:
        raise ValueError("Choose eureka or consul")
    for module in ["eureka-server", "service-client", "service-voiture"]:
        destination = ART / mode / (module + ".jar")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / module / "target" / (module + "-1.0.0.jar"), destination)
    environment(mode)
    try:
        for method in METHODS:
            stop_all()
            start(mode)
            benchmark(mode, method)
        if not SMOKE:
            for role in ["car", "discovery", "client"]:
                asyncio.run(fault(mode, role))
    finally:
        stop_all()
        for file in HERE.glob("*.log"):
            shutil.copyfile(file, RESULT / file.name)
        if STATE.exists():
            shutil.copyfile(STATE, RESULT / "processes-after-cleanup.json")


if __name__ == "__main__":
    main()
