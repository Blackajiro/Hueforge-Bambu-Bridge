import AppKit
import UniformTypeIdentifiers

struct PrinterPreset: Decodable {
    struct Bed: Decodable { let id: String; let name: String }
    let id: String
    let model: String
    let nozzle: String
    let beds: [Bed]
    let default_bed: String
}

final class BridgeApp: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    let projectLabel = NSTextField(labelWithString: "No project selected")
    let location = NSTextField(labelWithString: "Choose a saved HueForge project to get started.")
    let phase = NSTextField(labelWithString: "Connect your project")
    let status = NSTextField(wrappingLabelWithString: "Keep this app open while you work. Each new HueForge save becomes a Bambu Studio project.")
    let choose = NSButton(title: "Choose Project…", target: nil, action: nil)
    let stop = NSButton(title: "Disconnect", target: nil, action: nil)
    let open = NSButton(title: "Open in Bambu Studio", target: nil, action: nil)
    let reveal = NSButton(title: "Show in Finder", target: nil, action: nil)
    let autoOpen = NSButton(checkboxWithTitle: "Open Bambu Studio after export", target: nil, action: nil)
    let progress = NSProgressIndicator()
    let printerChoice = NSPopUpButton()
    let nozzleChoice = NSPopUpButton()
    let bedChoice = NSPopUpButton()
    var printers: [PrinterPreset] = []
    var selectedPreset: PrinterPreset? {
        printers.first { $0.model == printerChoice.titleOfSelectedItem && $0.nozzle + " mm" == nozzleChoice.titleOfSelectedItem }
    }
    var selectedBed: String? {
        selectedPreset?.beds.first { $0.name == bedChoice.titleOfSelectedItem }?.id
    }
    var projectURL: URL?
    var worker: Process?
    var latest: URL?
    var generation = UUID()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        let appMenu = NSMenuItem()
        menu.addItem(appMenu)
        appMenu.submenu = NSMenu()
        appMenu.submenu?.addItem(withTitle: "Quit HueForge Bambu Bridge", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let fileMenu = NSMenuItem(title: "File", action: nil, keyEquivalent: "")
        fileMenu.submenu = NSMenu(title: "File")
        let chooseItem = NSMenuItem(title: "Choose Project…", action: #selector(selectProject), keyEquivalent: "o")
        chooseItem.target = self
        fileMenu.submenu?.addItem(chooseItem); menu.addItem(fileMenu)
        let edit = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        menu.addItem(edit)
        edit.submenu = NSMenu(title: "Edit")
        edit.submenu?.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 620, height: 570),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.minSize = NSSize(width: 560, height: 590)
        window.title = "HueForge Bambu Bridge"
        window.center()
        let heading = NSTextField(wrappingLabelWithString: "Save in HueForge. Slice in Bambu.")
        heading.font = .systemFont(ofSize: 22, weight: .semibold)
        let detail = NSTextField(labelWithString: "Choose a printer. Keep your HueForge colors.")
        detail.textColor = .secondaryLabelColor
        detail.lineBreakMode = .byTruncatingTail
        let icon = NSImageView(image: NSImage(named: NSImage.applicationIconName) ?? NSImage())
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.widthAnchor.constraint(equalToConstant: 48).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 48).isActive = true
        let titleStack = NSStackView(views: [heading, detail])
        titleStack.orientation = .vertical; titleStack.alignment = .leading; titleStack.spacing = 6
        let header = NSStackView(views: [icon, titleStack]); header.spacing = 12
        projectLabel.font = .systemFont(ofSize: 14, weight: .medium)
        projectLabel.lineBreakMode = .byTruncatingMiddle; projectLabel.isSelectable = true
        location.font = .systemFont(ofSize: 12)
        location.textColor = .secondaryLabelColor
        location.lineBreakMode = .byTruncatingMiddle; location.isSelectable = true
        phase.font = .systemFont(ofSize: 15, weight: .semibold)
        status.maximumNumberOfLines = 3
        status.lineBreakMode = .byWordWrapping
        status.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        status.setAccessibilityRole(.staticText)
        progress.style = .spinning; progress.controlSize = .small
        progress.isDisplayedWhenStopped = false
        let phaseRow = NSStackView(views: [phase, progress]); phaseRow.spacing = 8
        printerChoice.target = self; printerChoice.action = #selector(printerChanged)
        nozzleChoice.target = self; nozzleChoice.action = #selector(nozzleChanged)
        bedChoice.target = self; bedChoice.action = #selector(selectionChanged)
        for popup in [printerChoice, nozzleChoice, bedChoice] { popup.isEnabled = false }
        printerChoice.addItem(withTitle: "Loading installed printers…")
        let printerGrid = NSGridView(views: [
            [NSTextField(labelWithString: "Printer"), printerChoice],
            [NSTextField(labelWithString: "Nozzle"), nozzleChoice],
            [NSTextField(labelWithString: "Build plate"), bedChoice]
        ])
        printerGrid.rowSpacing = 8; printerGrid.columnSpacing = 16
        printerGrid.column(at: 0).width = 90
        printerGrid.column(at: 0).xPlacement = .leading
        printerGrid.column(at: 1).xPlacement = .fill
        choose.isEnabled = false
        choose.target = self; choose.action = #selector(selectProject)
        stop.target = self; stop.action = #selector(disconnect); stop.isHidden = true
        open.target = self; open.action = #selector(openLatest); open.isEnabled = false
        reveal.target = self; reveal.action = #selector(revealLatest); reveal.isEnabled = false
        for button in [choose, stop, open, reveal] { button.bezelStyle = .rounded }
        choose.keyEquivalent = "\r"
        autoOpen.state = UserDefaults.standard.object(forKey: "autoOpen") == nil || UserDefaults.standard.bool(forKey: "autoOpen") ? .on : .off
        autoOpen.target = self; autoOpen.action = #selector(savePreference)
        let selection = NSStackView(views: [choose, stop]); selection.spacing = 8
        let output = NSStackView(views: [open, reveal]); output.spacing = 8
        let hint = NSTextField(wrappingLabelWithString: "Before printing, check the build plate and map project colors to your AMS spools in Bambu Studio.")
        hint.font = .systemFont(ofSize: 12); hint.textColor = .secondaryLabelColor
        let stack = NSStackView(views: [header, separator(), printerGrid, separator(), projectLabel, location, selection,
                                       separator(), phaseRow, status, autoOpen, output, hint])
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        var constraints = [
            header.widthAnchor.constraint(equalTo: stack.widthAnchor),
            printerGrid.widthAnchor.constraint(equalTo: stack.widthAnchor),
            heading.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -60),
            detail.widthAnchor.constraint(equalTo: heading.widthAnchor),
            stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: window.contentView!.bottomAnchor, constant: -24)
        ]
        for view in [projectLabel, location, status, hint] {
            constraints.append(view.widthAnchor.constraint(equalTo: stack.widthAnchor))
        }
        for view in stack.arrangedSubviews where view is NSBox {
            constraints.append(view.widthAnchor.constraint(equalTo: stack.widthAnchor))
        }
        NSLayoutConstraint.activate(constraints)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        loadPrinters()
    }

    func separator() -> NSBox { let box = NSBox(); box.boxType = .separator; return box }

    func updateStatus(_ title: String, _ message: String, busy: Bool = false, error: Bool = false) {
        phase.stringValue = title
        phase.textColor = error ? .systemRed : .labelColor
        status.stringValue = message; status.toolTip = message
        if busy { progress.startAnimation(nil) } else { progress.stopAnimation(nil) }
        NSAccessibility.post(element: status, notification: .valueChanged)
    }

    @objc func savePreference() { UserDefaults.standard.set(autoOpen.state == .on, forKey: "autoOpen") }

    func loadPrinters() {
        guard let resources = Bundle.main.resourceURL,
              let python = Bundle.main.object(forInfoDictionaryKey: "BridgePython") as? String else { return }
        updateStatus("Loading printers…", "Reading the presets installed with Bambu Studio.", busy: true)
        DispatchQueue.global(qos: .utility).async { [weak self] in
            do {
                let task = Process(); let output = Pipe(); let errors = Pipe()
                task.executableURL = URL(fileURLWithPath: python)
                task.arguments = [resources.appendingPathComponent("hueforge_bambu.py").path, "--list-printers"]
                task.standardOutput = output; task.standardError = errors
                try task.run()
                let data = output.fileHandleForReading.readDataToEndOfFile()
                task.waitUntilExit()
                guard task.terminationStatus == 0 else {
                    throw NSError(domain: "Bridge", code: 1, userInfo: [NSLocalizedDescriptionKey:
                        String(data: errors.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "Cannot read Bambu Studio presets."])
                }
                let entries = try JSONDecoder().decode([PrinterPreset].self, from: data)
                guard !entries.isEmpty else {
                    throw NSError(domain: "Bridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "Install Bambu Studio in /Applications to load its printer presets."])
                }
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.printers = entries
                    self.printerChoice.removeAllItems()
                    self.printerChoice.addItem(withTitle: "Select a printer…")
                    self.printerChoice.addItems(withTitles: Array(Set(entries.map { $0.model })).sorted())
                    self.printerChoice.isEnabled = true
                    if let saved = UserDefaults.standard.string(forKey: "printerModel"),
                       self.printerChoice.itemTitles.contains(saved) {
                        self.printerChoice.selectItem(withTitle: saved)
                        self.printerChanged()
                    } else {
                        self.updateStatus("Choose your printer", "If your model is missing, choose another as a starting point and change it in Bambu Studio before printing.")
                    }
                }
            } catch {
                DispatchQueue.main.async { self?.updateStatus("Could not load printers", error.localizedDescription, error: true) }
            }
        }
    }

    @objc func printerChanged() {
        disconnect()
        let matches = printers.filter { $0.model == printerChoice.titleOfSelectedItem }
        nozzleChoice.removeAllItems()
        let nozzles = Array(Set(matches.map { $0.nozzle })).sorted { (Double($0) ?? 0) < (Double($1) ?? 0) }
        nozzleChoice.addItems(withTitles: nozzles.map { $0 + " mm" })
        nozzleChoice.isEnabled = !nozzles.isEmpty
        let saved = UserDefaults.standard.string(forKey: "nozzle") ?? "0.4"
        if nozzles.contains(saved) { nozzleChoice.selectItem(withTitle: saved + " mm") }
        nozzleChanged()
    }

    @objc func nozzleChanged() {
        bedChoice.removeAllItems()
        if let preset = selectedPreset {
            bedChoice.addItems(withTitles: preset.beds.map { $0.name })
            let preferred = UserDefaults.standard.string(forKey: "bed") ?? preset.default_bed
            if let bed = preset.beds.first(where: { $0.id == preferred }) {
                bedChoice.selectItem(withTitle: bed.name)
            }
        }
        bedChoice.isEnabled = selectedPreset != nil
        selectionChanged()
    }

    @objc func selectionChanged() {
        disconnect()
        guard let preset = selectedPreset, let bed = selectedBed else { choose.isEnabled = false; return }
        UserDefaults.standard.set(preset.model, forKey: "printerModel")
        UserDefaults.standard.set(preset.nozzle, forKey: "nozzle")
        UserDefaults.standard.set(bed, forKey: "bed")
        choose.isEnabled = true
        updateStatus("Printer selected", "Choose a HueForge project. You can change the printer and settings later in Bambu Studio.")
        if let project = projectURL { connect(project) }
    }

    @objc func selectProject() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "hfp") ?? .data]
        panel.canChooseDirectories = false; panel.allowsMultipleSelection = false
        panel.prompt = "Connect Project"
        panel.message = "Select the saved .hfp file. Keep its matching Front STL in the same folder."
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let url = panel.url else { return }
            self?.connect(url)
        }
    }

    func connect(_ url: URL) {
        guard let preset = selectedPreset, let bed = selectedBed else { return }
        projectURL = url
        disconnect()
        latest = nil; open.isEnabled = false; reveal.isEnabled = false
        projectLabel.stringValue = url.lastPathComponent
        location.stringValue = url.deletingLastPathComponent().path
        location.toolTip = url.path
        guard let resources = Bundle.main.resourceURL,
              let python = Bundle.main.object(forInfoDictionaryKey: "BridgePython") as? String,
              FileManager.default.isExecutableFile(atPath: python) else {
            updateStatus("Python not found", "Rebuild this app with python3 macos/build.py on this Mac.", error: true)
            return
        }
        guard FileManager.default.fileExists(atPath: "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio") else {
            updateStatus("Bambu Studio not found", "Install Bambu Studio in /Applications, then choose the project again.", error: true)
            return
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: python)
        task.arguments = [resources.appendingPathComponent("watch_hueforge.py").path, url.path, "--printer", preset.id, "--bed", bed]
        task.currentDirectoryURL = resources
        let pipe = Pipe(); task.standardOutput = pipe; task.standardError = FileHandle.nullDevice
        let token = UUID(); generation = token; worker = task
        task.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, self.generation == token else { return }
                self.stop.isHidden = true; self.worker = nil
                self.progress.stopAnimation(nil)
                if self.phase.textColor != .systemRed {
                    self.updateStatus("Disconnected", "Choose the project again to resume automatic exports.")
                }
            }
        }
        do {
            try task.run()
            stop.isHidden = false; choose.title = "Change Project…"
            updateStatus("Connecting…", "Reading your saved project and looking for its Front STL.", busy: true)
            DispatchQueue.global(qos: .utility).async { [weak self] in
                var pending = Data()
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    pending.append(data)
                    while let end = pending.firstIndex(of: 10) {
                        let line = pending.prefix(upTo: end); pending.removeSubrange(...end)
                        guard let event = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
                        DispatchQueue.main.async {
                            guard let self = self, self.generation == token else { return }
                            self.receive(event)
                        }
                    }
                }
            }
        } catch { worker = nil; updateStatus("Could not connect", error.localizedDescription, error: true) }
    }

    func receive(_ event: [String: Any]) {
        let kind = event["event"] as? String ?? ""
        let message = event["message"] as? String ?? ""
        switch kind {
        case "connected": updateStatus("Waiting for your next save", message)
        case "waiting": updateStatus("Save in progress", message, busy: true)
        case "converting": updateStatus("Exporting 3MF…", message, busy: true)
        case "error": updateStatus("Export needs attention", message, error: true)
        case "ready":
            guard let path = event["path"] as? String else { return }
            latest = URL(fileURLWithPath: path)
            open.isEnabled = true; reveal.isEnabled = true
            updateStatus("3MF exported", message)
            if autoOpen.state == .on { openLatest() }
        default: break
        }
    }

    @objc func disconnect() {
        generation = UUID(); worker?.terminate(); worker = nil
        stop.isHidden = true; choose.title = "Choose Project…"
        updateStatus("Disconnected", "Choose a project to resume. Your existing exports are kept.")
    }

    @objc func revealLatest() {
        if let file = latest { NSWorkspace.shared.activateFileViewerSelecting([file]) }
    }

    @objc func openLatest() {
        guard let file = latest else { return }
        let token = generation
        NSWorkspace.shared.open([file], withApplicationAt: URL(fileURLWithPath: "/Applications/BambuStudio.app"), configuration: NSWorkspace.OpenConfiguration()) { [weak self] _, error in
            DispatchQueue.main.async {
                guard let self = self, self.generation == token else { return }
                if let error = error {
                    self.updateStatus("3MF saved; could not open Studio", error.localizedDescription + " Use Show in Finder to open the file manually.", error: true)
                }
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
