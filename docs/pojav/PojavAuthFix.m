#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

typedef void (^PAFStatusBlock)(id status, BOOL success);
typedef void (^PAFXSTSBlock)(NSString *xsts, NSString *uhs);

static BOOL gReportHooked = NO;
static BOOL gXboxHooked = NO;
static BOOL gTraceHooked = NO;
static BOOL gAnnounced = NO;
static BOOL gResultShown = NO;
static NSMutableArray<NSString *> *gTrace = nil;
static NSMutableDictionary<NSNumber *, NSMutableData *> *gBodies = nil;
static NSObject *gTraceLock = nil;

static void PAFTraceAdd(NSString *line) {
    @synchronized (gTraceLock) {
        [gTrace addObject:line];
        if (gTrace.count > 40) {
            [gTrace removeObjectAtIndex:0];
        }
    }
}

static NSString *PAFTraceText(void) {
    @synchronized (gTraceLock) {
        return gTrace.count > 0 ? [gTrace componentsJoinedByString:@"\n"] : @"no requests were recorded";
    }
}

static void PAFTraceReset(void) {
    @synchronized (gTraceLock) {
        [gTrace removeAllObjects];
        [gBodies removeAllObjects];
    }
}

static NSString *PAFDescribe(NSError *error) {
    NSMutableArray *lines = [NSMutableArray arrayWithObject:error.localizedDescription ?: @"Unknown error"];
    NSURL *url = error.userInfo[NSURLErrorFailingURLErrorKey];
    if ([url isKindOfClass:NSURL.class]) {
        NSURLComponents *parts = [NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO];
        parts.query = nil;
        [lines addObject:parts.URL.absoluteString ?: (url.host ?: @"")];
    }
    NSHTTPURLResponse *response = error.userInfo[@"com.alamofire.serialization.response.error.response"];
    if ([response isKindOfClass:NSHTTPURLResponse.class]) {
        [lines addObject:[NSString stringWithFormat:@"HTTP %ld", (long)response.statusCode]];
    }
    NSData *data = error.userInfo[@"com.alamofire.serialization.response.error.data"];
    if ([data isKindOfClass:NSData.class] && data.length > 0) {
        NSString *body = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        if (body.length > 700) {
            body = [body substringToIndex:700];
        }
        if (body) {
            [lines addObject:body];
        }
    }
    NSError *underlying = error.userInfo[NSUnderlyingErrorKey];
    if ([underlying isKindOfClass:NSError.class]) {
        [lines addObject:underlying.localizedDescription ?: @""];
    }
    return [lines componentsJoinedByString:@"\n"];
}

static UIViewController *PAFTopViewController(void) {
    UIWindow *window = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class]) {
            continue;
        }
        for (UIWindow *candidate in ((UIWindowScene *)scene).windows) {
            if (candidate.isKeyWindow) {
                window = candidate;
            }
        }
    }
    if (window == nil) {
        window = UIApplication.sharedApplication.windows.firstObject;
    }
    UIViewController *top = window.rootViewController;
    while (top.presentedViewController) {
        top = top.presentedViewController;
    }
    return top;
}

static void PAFPresentWhenReady(UIAlertController *alert, int attempt) {
    UIViewController *top = PAFTopViewController();
    BOOL busy = top == nil || top.isBeingPresented || top.isBeingDismissed || top.transitionCoordinator != nil;
    if (busy && attempt < 24) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(NSEC_PER_SEC * 3 / 4)), dispatch_get_main_queue(), ^{
            PAFPresentWhenReady(alert, attempt + 1);
        });
        return;
    }
    if (top == nil) {
        return;
    }
    [top presentViewController:alert animated:YES completion:nil];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(NSEC_PER_SEC * 3 / 5)), dispatch_get_main_queue(), ^{
        if (alert.presentingViewController == nil && attempt < 24) {
            PAFPresentWhenReady(alert, attempt + 1);
        }
    });
}

static void PAFPresentTitled(NSString *title, NSString *text) {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:title
                                                                       message:text
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"Copy" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
            UIPasteboard.generalPasteboard.string = text;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleCancel handler:nil]];
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)NSEC_PER_SEC), dispatch_get_main_queue(), ^{
            PAFPresentWhenReady(alert, 0);
        });
    });
}

static void PAFPresent(NSString *text) {
    PAFPresentTitled(@"Sign-in failed", text);
}

static BOOL PAFHookTrace(void) {
    Class cls = objc_getClass("AFURLSessionManager");
    SEL dataSelector = NSSelectorFromString(@"URLSession:dataTask:didReceiveData:");
    SEL doneSelector = NSSelectorFromString(@"URLSession:task:didCompleteWithError:");
    Method data = cls ? class_getInstanceMethod(cls, dataSelector) : NULL;
    Method done = cls ? class_getInstanceMethod(cls, doneSelector) : NULL;
    if (data == NULL || done == NULL) {
        return NO;
    }
    IMP dataOriginal = method_getImplementation(data);
    method_setImplementation(data, imp_implementationWithBlock(^(id self, NSURLSession *session, NSURLSessionDataTask *task, NSData *chunk) {
        @synchronized (gTraceLock) {
            NSNumber *key = @(task.taskIdentifier);
            NSMutableData *body = gBodies[key];
            if (body == nil) {
                body = [NSMutableData data];
                gBodies[key] = body;
            }
            if (body.length < 1500) {
                [body appendData:chunk];
            }
        }
        ((void (*)(id, SEL, id, id, id))dataOriginal)(self, dataSelector, session, task, chunk);
    }));
    IMP doneOriginal = method_getImplementation(done);
    method_setImplementation(done, imp_implementationWithBlock(^(id self, NSURLSession *session, NSURLSessionTask *task, NSError *error) {
        NSURL *url = task.originalRequest.URL;
        NSHTTPURLResponse *response = [task.response isKindOfClass:NSHTTPURLResponse.class] ? (NSHTTPURLResponse *)task.response : nil;
        NSString *result = response ? [NSString stringWithFormat:@"%ld", (long)response.statusCode] : (error.localizedDescription ?: @"no response");
        NSString *line = [NSString stringWithFormat:@"%@ %@%@ -> %@", task.originalRequest.HTTPMethod ?: @"?", url.host ?: @"", url.path ?: @"", result];
        if (response && response.statusCode >= 400) {
            NSData *body = nil;
            @synchronized (gTraceLock) {
                body = [gBodies[@(task.taskIdentifier)] copy];
            }
            NSString *text = body.length > 0 ? [[NSString alloc] initWithData:body encoding:NSUTF8StringEncoding] : nil;
            if (text.length > 350) {
                text = [text substringToIndex:350];
            }
            if (text.length > 0) {
                line = [line stringByAppendingFormat:@"\n   %@", text];
            }
        }
        @synchronized (gTraceLock) {
            [gBodies removeObjectForKey:@(task.taskIdentifier)];
        }
        PAFTraceAdd(line);
        ((void (*)(id, SEL, id, id, id))doneOriginal)(self, doneSelector, session, task, error);
    }));
    return YES;
}

static BOOL PAFHookLoginStart(void) {
    Class cls = objc_getClass("AccountListViewController");
    SEL selector = NSSelectorFromString(@"actionLoginMicrosoft:");
    Method method = cls ? class_getInstanceMethod(cls, selector) : NULL;
    if (method == NULL) {
        return NO;
    }
    IMP original = method_getImplementation(method);
    method_setImplementation(method, imp_implementationWithBlock(^(id self, id sender) {
        PAFTraceReset();
        gResultShown = NO;
        PAFTraceAdd(@"Microsoft login tapped");
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(45 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            if (!gResultShown) {
                gResultShown = YES;
                PAFPresent([NSString stringWithFormat:@"Still no result after 45 seconds.\n\n%@", PAFTraceText()]);
            }
        });
        ((void (*)(id, SEL, id))original)(self, selector, sender);
    }));
    return YES;
}

static BOOL PAFHookFailureReport(void) {
    Class cls = objc_getClass("AccountListViewController");
    SEL selector = NSSelectorFromString(@"callbackMicrosoftAuth:success:forCell:");
    Method method = cls ? class_getInstanceMethod(cls, selector) : NULL;
    if (method == NULL) {
        return NO;
    }
    IMP original = method_getImplementation(method);
    IMP replacement = imp_implementationWithBlock(^(id self, id status, BOOL success, id cell) {
        gResultShown = YES;
        NSString *report = nil;
        if (!success && [status isKindOfClass:NSError.class]) {
            report = [NSString stringWithFormat:@"%@\n\nRequests:\n%@", PAFDescribe(status), PAFTraceText()];
            UIPasteboard.generalPasteboard.string = report;
            PAFPresent(report);
        }
        ((void (*)(id, SEL, id, BOOL, id))original)(self, selector, status, success, cell);
        if (report != nil && [cell isKindOfClass:UITableViewCell.class]) {
            UITableViewCell *row = cell;
            row.detailTextLabel.numberOfLines = 0;
            row.detailTextLabel.text = [PAFTraceText() stringByAppendingString:@"\n(details copied to clipboard)"];
        }
    });
    method_setImplementation(method, replacement);
    return YES;
}

static BOOL PAFHookXboxProfile(void) {
    Class cls = objc_getClass("MicrosoftAuthenticator");
    if (cls == nil) {
        return NO;
    }
    SEL profileSelector = NSSelectorFromString(@"acquireXboxProfile:xstsToken:callback:");
    Method profile = class_getInstanceMethod(cls, profileSelector);
    SEL xstsSelector = NSSelectorFromString(@"acquireXSTSFor:token:xstsCallback:callback:");
    Method xsts = class_getInstanceMethod(cls, xstsSelector);
    if (profile == NULL || xsts == NULL) {
        return NO;
    }
    method_setImplementation(profile, imp_implementationWithBlock(^(id self, NSString *uhs, NSString *token, PAFStatusBlock callback) {
        callback(nil, YES);
    }));
    IMP original = method_getImplementation(xsts);
    method_setImplementation(xsts, imp_implementationWithBlock(^(id self, NSString *party, NSString *token, PAFXSTSBlock xstsCallback, PAFStatusBlock callback) {
        if ([party hasPrefix:@"http://xboxlive.com"]) {
            xstsCallback(@"skipped", @"skipped");
            return;
        }
        ((void (*)(id, SEL, id, id, id, id))original)(self, xstsSelector, party, token, xstsCallback, callback);
    }));
    return YES;
}

static BOOL gLoginHooked = NO;

static void PAFInstall(void) {
    if (!gTraceHooked) {
        gTraceHooked = PAFHookTrace();
    }
    if (!gLoginHooked) {
        gLoginHooked = PAFHookLoginStart();
    }
    if (!gReportHooked) {
        gReportHooked = PAFHookFailureReport();
    }
    if (!gXboxHooked) {
        gXboxHooked = PAFHookXboxProfile();
    }
}

static void PAFAnnounce(void) {
    if (gAnnounced) {
        return;
    }
    gAnnounced = YES;
    NSString *text = [NSString stringWithFormat:@"Library loaded.\nFailure report hook: %@\nXbox skip hook: %@\nRequest log hook: %@\nLogin start hook: %@",
                      gReportHooked ? @"on" : @"missing", gXboxHooked ? @"on" : @"missing",
                      gTraceHooked ? @"on" : @"missing", gLoginHooked ? @"on" : @"missing"];
    PAFPresentTitled(@"PojavAuthFix", text);
}

static void PAFRetry(int attempt) {
    PAFInstall();
    if ((gReportHooked && gXboxHooked && gTraceHooked && gLoginHooked) || attempt >= 10) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            PAFAnnounce();
        });
        return;
    }
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(NSEC_PER_SEC / 2)), dispatch_get_main_queue(), ^{
        PAFRetry(attempt + 1);
    });
}

__attribute__((constructor)) static void PAFInit(void) {
    gTrace = [NSMutableArray array];
    gBodies = [NSMutableDictionary dictionary];
    gTraceLock = [NSObject new];
    PAFInstall();
    dispatch_async(dispatch_get_main_queue(), ^{
        PAFRetry(0);
    });
}
