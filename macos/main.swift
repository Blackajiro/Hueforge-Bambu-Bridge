import AppKit
import UniformTypeIdentifiers

final class BridgeApp: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    let projectLabel = NSTextField(labelWithString: "Nessun progetto collegato")
    let status = NSTextField(wrappingLabelWithString: "Scegli un progetto. Poi salva in HueForge: il 3MF viene preparato automaticamente.")
    let choose = NSButton(title: "Scegli progetto HueForge…", target: nil, action: nil)
    let stop = NSButton(title: "Scollega", target: nil, action: nil)
    let open = NSButton(title: "Apri ultimo 3MF", target: nil, action: nil)
    let autoOpen = NSButton(checkboxWithTitle: "Apri in Bambu Studio dopo ogni esportazione", target: nil, action: nil)
    var worker: Process?
    var latest: URL?
    var generation = UUID()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        let appMenu = NSMenuItem()
        menu.addItem(appMenu)
        appMenu.submenu = NSMenu()
        appMenu.submenu?.addItem(withTitle: "Esci da HueForge Bambu Bridge", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let edit = NSMenuItem(title: "Modifica", action: nil, keyEquivalent: "")
        menu.addItem(edit)
        edit.submenu = NSMenu(title: "Modifica")
        edit.submenu?.addItem(withTitle: "Copia", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 530, height: 360),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "HueForge Bambu Bridge"
        window.center()
        let heading = NSTextField(labelWithString: "Da HueForge a Bambu Studio")
        heading.font = .systemFont(ofSize: 21, weight: .semibold)
        let detail = NSTextField(labelWithString: "P2S · ugello 0,4 mm · AMS")
        detail.textColor = .secondaryLabelColor
        projectLabel.lineBreakMode = .byTruncatingMiddle
        projectLabel.isSelectable = true
        status.maximumNumberOfLines = 3
        status.lineBreakMode = .byTruncatingTail
        status.textColor = .secondaryLabelColor
        status.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        choose.target = self; choose.action = #selector(selectProject)
        choose.bezelStyle = .rounded
        stop.target = self; stop.action = #selector(disconnect)
        stop.bezelStyle = .rounded; stop.isEnabled = false
        open.target = self; open.action = #selector(openLatest)
        open.bezelStyle = .rounded; open.isEnabled = false
        autoOpen.state = .on
        let buttons = NSStackView(views: [choose, stop])
        buttons.spacing = 8
        let stack = NSStackView(views: [heading, detail, projectLabel, buttons, status, autoOpen, open])
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 14
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 24),
            status.widthAnchor.constraint(equalTo: stack.widthAnchor),
            projectLabel.widthAnchor.constraint(equalTo: stack.widthAnchor)
        ])
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func selectProject() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "hfp") ?? .data]
        panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
        panel.prompt = "Collega progetto"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        disconnect()
        latest = nil; open.isEnabled = false
        projectLabel.stringValue = url.lastPathComponent
        projectLabel.toolTip = url.path
        guard let resources = Bundle.main.resourceURL,
              let python = Bundle.main.object(forInfoDictionaryKey: "BridgePython") as? String,
              FileManager.default.isExecutableFile(atPath: python) else {
            status.stringValue = "Python 3 non trovato. Ricostruisci l’app con python3 macos/build.py."
            return
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: python)
        task.arguments = [resources.appendingPathComponent("watch_hueforge.py").path, url.path]
        task.currentDirectoryURL = resources
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice
        let token = UUID(); generation = token
        worker = task
        task.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, self.generation == token else { return }
                self.stop.isEnabled = false
                self.worker = nil
                if !self.status.stringValue.hasPrefix("Errore:") {
                    self.status.stringValue = "Bridge arrestato. Scegli il progetto per ripartire."
                }
            }
        }
        do {
            try task.run()
            stop.isEnabled = true
            status.stringValue = "Collegamento al progetto…"
            DispatchQueue.global(qos: .utility).async { [weak self] in
                var pending = Data()
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    pending.append(data)
                    while let end = pending.firstIndex(of: 10) {
                        let line = pending.prefix(upTo: end)
                        pending.removeSubrange(...end)
                        guard let event = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
                        DispatchQueue.main.async {
                            guard let self = self, self.generation == token else { return }
                            self.receive(event)
                        }
                    }
                }
            }
        } catch {
            worker = nil
            status.stringValue = "Errore: \(error.localizedDescription)"
        }
    }

    func receive(_ event: [String: Any]) {
        let kind = event["event"] as? String ?? ""
        status.stringValue = (kind == "error" ? "Errore: " : "") + (event["message"] as? String ?? "")
        status.toolTip = status.stringValue
        if kind == "ready", let path = event["path"] as? String {
            latest = URL(fileURLWithPath: path)
            open.isEnabled = true
            if autoOpen.state == .on { openLatest() }
        }
    }

    @objc func disconnect() {
        generation = UUID()
        worker?.terminate(); worker = nil
        stop.isEnabled = false
        status.stringValue = "Scollegato. Puoi scegliere un progetto HueForge."
    }

    @objc func openLatest() {
        guard let file = latest else { return }
        let app = URL(fileURLWithPath: "/Applications/BambuStudio.app")
        NSWorkspace.shared.open([file], withApplicationAt: app, configuration: NSWorkspace.OpenConfiguration()) { [weak self] _, error in
            if let error = error {
                DispatchQueue.main.async { self?.status.stringValue = "3MF creato, apertura non riuscita: \(error.localizedDescription)" }
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) { worker?.terminate() }
}

let app = NSApplication.shared
let delegate = BridgeApp()
app.delegate = delegate
app.run()
